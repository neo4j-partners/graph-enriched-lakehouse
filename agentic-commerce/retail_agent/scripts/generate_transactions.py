#!/usr/bin/env python3
"""Generate large-scale retail transaction dataset (500,000 orders).

Integrates with existing Neo4j product catalog from product_catalog.py.
Outputs CSV files to data/lakehouse/ for Databricks Delta Lake ingestion.
"""

import argparse
import csv
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple, Sequence

from pydantic import BaseModel, Field

from retail_agent.data.product_catalog import (
    CATEGORIES,
    PRODUCTS,
    Product,
    generate_expanded_catalog,
)
from retail_agent.data.product_knowledge import (
    KNOWLEDGE_ARTICLES,
    KnowledgeArticle,
    REVIEWS as PRODUCT_REVIEWS,
    Review as ProductReview,
    SUPPORT_TICKETS,
    SupportTicket,
)


# ---------------------------------------------------------------------------
# Pydantic models — record schemas
# ---------------------------------------------------------------------------


class Customer(BaseModel):
    customer_id: str
    segment: str
    signup_date: str
    preferred_channel: str
    city: str
    state: str
    age_group: str


class Store(BaseModel):
    store_id: str
    store_name: str
    city: str
    state: str
    region: str
    opened_date: str


class Transaction(BaseModel):
    transaction_id: str
    order_id: str
    customer_id: str
    product_id: str
    product_name: str
    category: str
    brand: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0)
    discount_pct: float = Field(ge=0, le=1)
    total_price: float = Field(ge=0)
    purchase_date: str
    purchase_hour: int = Field(ge=0, le=23)
    day_of_week: str
    channel: str
    store_id: str
    payment_method: str
    returned: bool
    return_date: str
    return_reason: str


class Review(BaseModel):
    review_id: str
    transaction_id: str
    customer_id: str
    product_id: str
    rating: int = Field(ge=1, le=5)
    review_date: str
    verified_purchase: bool = True


class InventorySnapshot(BaseModel):
    snapshot_date: str
    product_id: str
    stock_level: int
    units_sold: int
    units_received: int
    stock_status: str


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class GeneratorConfig(BaseModel):
    """All tuneable parameters for the data generator."""

    num_orders: int = 500_000
    num_customers: int = 5_000
    num_stores: int = 20
    review_rate: float = 0.10
    start_date: datetime = datetime(2023, 1, 1)
    end_date: datetime = datetime(2024, 12, 31)
    seed: int = 42
    output_dir: Path = Path(__file__).resolve().parents[2] / "data" / "lakehouse"
    expanded: bool = False


# ---------------------------------------------------------------------------
# Weighted distributions (from LAKEHOUSE.md spec)
# ---------------------------------------------------------------------------

# Seasonal multipliers applied to daily order volume (month index 1-12)
SEASONAL_MULTIPLIERS: dict[int, float] = {
    1: 0.8, 2: 0.8,       # Jan-Feb: post-holiday dip
    3: 1.1, 4: 1.1,       # Mar-Apr: spring buying
    5: 1.2, 6: 1.2,       # May-Jun: summer prep
    7: 0.9, 8: 0.9,       # Jul-Aug: summer lull
    9: 1.3, 10: 1.3,      # Sep-Oct: back-to-school, fall running season
    11: 1.5, 12: 1.5,     # Nov-Dec: holiday peak
}

# Category purchase frequency weights
CATEGORY_WEIGHTS: dict[str, int] = {
    "Running Shoes": 25,
    "Casual Shoes": 15,
    "Apparel": 20,
    "Accessories": 12,
    "Equipment": 8,
    "Nutrition": 10,
    "Outdoor": 10,
    "Outdoor Equipment": 8,
}

# Customer segment definitions

class SegmentConfig(BaseModel):
    """Purchasing behavior parameters for a customer segment."""

    weight: int
    avg_orders_year: int
    avg_basket: float
    discount_range: tuple[int, int]
    brand_loyalty: str


CUSTOMER_SEGMENTS: dict[str, SegmentConfig] = {
    "loyal":          SegmentConfig(weight=20, avg_orders_year=12, avg_basket=2.5, discount_range=(0, 10),  brand_loyalty="high"),
    "occasional":     SegmentConfig(weight=35, avg_orders_year=4,  avg_basket=1.5, discount_range=(5, 15),  brand_loyalty="medium"),
    "new":            SegmentConfig(weight=25, avg_orders_year=2,  avg_basket=1.2, discount_range=(10, 25), brand_loyalty="low"),
    "bargain_hunter": SegmentConfig(weight=20, avg_orders_year=8,  avg_basket=3.0, discount_range=(15, 30), brand_loyalty="low"),
}

# Time-of-day purchase hour weights (24 buckets)
HOUR_WEIGHTS: list[int] = [
    # 0-5: overnight (low)
    1, 1, 1, 1, 1, 1,
    # 6-8: early morning (10%)
    3, 4, 3,
    # 9-11: morning (20%)
    7, 7, 6,
    # 12-13: lunch spike (15%)
    8, 7,
    # 14-16: afternoon (15%)
    5, 5, 5,
    # 17-20: evening peak (30%)
    8, 9, 9, 4,
    # 21-23: late night (low)
    3, 2, 1,
]

# Channel distribution
CHANNELS: list[str] = ["online", "in_store", "mobile_app"]
CHANNEL_WEIGHTS: list[int] = [60, 25, 15]

# Payment methods
PAYMENT_METHODS: list[str] = ["credit_card", "debit_card", "paypal", "apple_pay"]
PAYMENT_WEIGHTS: list[int] = [45, 25, 20, 10]

# Return rates by category
RETURN_RATES: dict[str, float] = {
    "Running Shoes": 0.12,
    "Casual Shoes": 0.10,
    "Apparel": 0.15,
    "Accessories": 0.05,
    "Equipment": 0.08,
    "Nutrition": 0.03,
    "Outdoor": 0.10,
    "Outdoor Equipment": 0.10,
}

RETURN_REASONS: list[str] = ["wrong_size", "defective", "changed_mind", "not_as_described"]
RETURN_REASON_WEIGHTS: list[int] = [40, 15, 30, 15]

QUANTITY_OPTIONS: list[int] = [1, 2, 3, 4, 5]
QUANTITY_WEIGHTS: list[int] = [60, 20, 10, 6, 4]

AGE_GROUPS: list[str] = ["18-24", "25-34", "35-44", "45-54", "55+"]
AGE_GROUP_WEIGHTS: list[int] = [15, 30, 25, 18, 12]


# ---------------------------------------------------------------------------
# US cities
# ---------------------------------------------------------------------------


class City(NamedTuple):
    name: str
    state: str
    region: str


US_CITIES: list[City] = [
    City("New York", "NY", "northeast"),
    City("Los Angeles", "CA", "west"),
    City("Chicago", "IL", "midwest"),
    City("Houston", "TX", "southwest"),
    City("Phoenix", "AZ", "southwest"),
    City("Philadelphia", "PA", "northeast"),
    City("San Antonio", "TX", "southwest"),
    City("San Diego", "CA", "west"),
    City("Dallas", "TX", "southwest"),
    City("Austin", "TX", "southwest"),
    City("San Francisco", "CA", "west"),
    City("Seattle", "WA", "west"),
    City("Denver", "CO", "west"),
    City("Boston", "MA", "northeast"),
    City("Nashville", "TN", "southeast"),
    City("Portland", "OR", "west"),
    City("Atlanta", "GA", "southeast"),
    City("Miami", "FL", "southeast"),
    City("Minneapolis", "MN", "midwest"),
    City("Charlotte", "NC", "southeast"),
    City("Detroit", "MI", "midwest"),
    City("Orlando", "FL", "southeast"),
    City("Tampa", "FL", "southeast"),
    City("St. Louis", "MO", "midwest"),
    City("Baltimore", "MD", "northeast"),
    City("Salt Lake City", "UT", "west"),
    City("Indianapolis", "IN", "midwest"),
    City("Cleveland", "OH", "midwest"),
    City("Kansas City", "MO", "midwest"),
    City("Raleigh", "NC", "southeast"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _products_by_category(products: Sequence[Product]) -> dict[str, list[Product]]:
    """Index products by category name."""
    by_cat: dict[str, list[Product]] = defaultdict(list)
    for p in products:
        by_cat[p.category].append(p)
    return dict(by_cat)


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def generate_customers(config: GeneratorConfig, rng: random.Random) -> list[Customer]:
    segments = list(CUSTOMER_SEGMENTS.keys())
    seg_weights = [CUSTOMER_SEGMENTS[s].weight for s in segments]

    customers: list[Customer] = []
    for i in range(1, config.num_customers + 1):
        city = rng.choice(US_CITIES)
        customers.append(
            Customer(
                customer_id=f"CUST{i:05d}",
                segment=rng.choices(segments, weights=seg_weights, k=1)[0],
                signup_date=f"{rng.randint(2020, 2024)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                preferred_channel=rng.choices(CHANNELS, weights=CHANNEL_WEIGHTS, k=1)[0],
                city=city.name,
                state=city.state,
                age_group=rng.choices(AGE_GROUPS, weights=AGE_GROUP_WEIGHTS, k=1)[0],
            )
        )
    return customers


def generate_stores(config: GeneratorConfig, rng: random.Random) -> list[Store]:
    store_cities = rng.sample(US_CITIES, min(config.num_stores, len(US_CITIES)))
    stores: list[Store] = []
    for i, city in enumerate(store_cities, 1):
        stores.append(
            Store(
                store_id=f"STORE{i:03d}",
                store_name=f"{city.name} Store",
                city=city.name,
                state=city.state,
                region=city.region,
                opened_date=f"{rng.randint(2015, 2022)}-{rng.randint(1, 12):02d}-01",
            )
        )
    return stores


def _generate_line_item(
    *,
    txn_id: str,
    order_id: str,
    customer_id: str,
    purchase_ts: datetime,
    day_of_week: str,
    channel: str,
    store_id: str,
    payment: str,
    product: Product,
    category: str,
    disc_lo: int,
    disc_hi: int,
    rng: random.Random,
) -> dict:
    """Build a single transaction line-item dict.

    Returns a plain dict for performance (1M+ records).  The ``Transaction``
    model documents the schema and is used for sample validation.
    """
    quantity = rng.choices(QUANTITY_OPTIONS, weights=QUANTITY_WEIGHTS, k=1)[0]
    discount_pct = round(rng.uniform(disc_lo, disc_hi) / 100, 4)
    total_price = round(quantity * product.price * (1 - discount_pct), 2)

    returned = rng.random() < RETURN_RATES.get(category, 0.08)
    return_date = ""
    return_reason = ""
    if returned:
        ret_dt = purchase_ts + timedelta(days=rng.randint(1, 30))
        return_date = ret_dt.strftime("%Y-%m-%d %H:%M:%S")
        return_reason = rng.choices(RETURN_REASONS, weights=RETURN_REASON_WEIGHTS, k=1)[0]

    return {
        "transaction_id": txn_id,
        "order_id": order_id,
        "customer_id": customer_id,
        "product_id": product.id,
        "product_name": product.name,
        "category": category,
        "brand": product.brand,
        "quantity": quantity,
        "unit_price": product.price,
        "discount_pct": discount_pct,
        "total_price": total_price,
        "purchase_date": purchase_ts.strftime("%Y-%m-%d %H:%M:%S"),
        "purchase_hour": purchase_ts.hour,
        "day_of_week": day_of_week,
        "channel": channel,
        "store_id": store_id,
        "payment_method": payment,
        "returned": returned,
        "return_date": return_date,
        "return_reason": return_reason,
    }


def generate_transactions(
    products: Sequence[Product],
    customers: list[Customer],
    stores: list[Store],
    config: GeneratorConfig,
    rng: random.Random,
) -> list[dict]:
    """Generate ``config.num_orders`` orders, each with 1+ line items.

    Returns plain dicts for performance.  Use the ``Transaction`` model
    for schema documentation and sample validation.
    """
    by_cat = _products_by_category(products)

    # Only include categories that have products in the catalog
    valid_cats = [c for c in CATEGORY_WEIGHTS if c in by_cat]
    valid_cat_weights = [CATEGORY_WEIGHTS[c] for c in valid_cats]

    store_ids = [s.store_id for s in stores]
    cust_segments = {c.customer_id: c.segment for c in customers}

    total_days = (config.end_date - config.start_date).days + 1

    # Distribute orders across days using seasonal weighting
    day_weights = [
        SEASONAL_MULTIPLIERS[( config.start_date + timedelta(days=d)).month]
        for d in range(total_days)
    ]
    order_days = rng.choices(range(total_days), weights=day_weights, k=config.num_orders)

    # Assign each order to a customer, weighted by segment purchase frequency
    cust_ids = [c.customer_id for c in customers]
    cust_order_weights = [CUSTOMER_SEGMENTS[c.segment].avg_orders_year for c in customers]
    order_customers = rng.choices(cust_ids, weights=cust_order_weights, k=config.num_orders)

    transactions: list[dict] = []
    txn_seq = 0

    for order_idx in range(config.num_orders):
        purchase_date = config.start_date + timedelta(days=order_days[order_idx])
        date_str = purchase_date.strftime("%Y%m%d")

        customer_id = order_customers[order_idx]
        seg_config = CUSTOMER_SEGMENTS[cust_segments[customer_id]]

        order_id = f"ORD{date_str}{order_idx:06d}"

        # Basket size from segment average (Gaussian, clamped)
        avg_basket: float = seg_config.avg_basket
        basket_size = max(1, min(8, int(rng.gauss(avg_basket, avg_basket * 0.4) + 0.5)))

        channel = rng.choices(CHANNELS, weights=CHANNEL_WEIGHTS, k=1)[0]
        store_id = rng.choice(store_ids) if channel == "in_store" else ""
        purchase_hour = rng.choices(range(24), weights=HOUR_WEIGHTS, k=1)[0]
        payment = rng.choices(PAYMENT_METHODS, weights=PAYMENT_WEIGHTS, k=1)[0]
        day_of_week = purchase_date.strftime("%A")
        disc_lo, disc_hi = seg_config.discount_range

        for _ in range(basket_size):
            txn_seq += 1
            cat = rng.choices(valid_cats, weights=valid_cat_weights, k=1)[0]
            product = rng.choice(by_cat[cat])

            purchase_ts = purchase_date.replace(
                hour=purchase_hour,
                minute=rng.randint(0, 59),
                second=rng.randint(0, 59),
            )

            transactions.append(
                _generate_line_item(
                    txn_id=f"TXN{date_str}{txn_seq:06d}",
                    order_id=order_id,
                    customer_id=customer_id,
                    purchase_ts=purchase_ts,
                    day_of_week=day_of_week,
                    channel=channel,
                    store_id=store_id,
                    payment=payment,
                    product=product,
                    category=cat,
                    disc_lo=disc_lo,
                    disc_hi=disc_hi,
                    rng=rng,
                )
            )

        if (order_idx + 1) % 100_000 == 0:
            print(f"  Generated {order_idx + 1:,} orders ({len(transactions):,} line items)...")

    return transactions


def generate_reviews(
    transactions: list[dict],
    config: GeneratorConfig,
    rng: random.Random,
) -> list[dict]:
    """Generate reviews for ~10% of transaction line items.

    Returns plain dicts.  Use the ``Review`` model for schema docs.
    """
    ratings = [1, 2, 3, 4, 5]
    rating_weights = [3, 5, 12, 35, 45]

    reviews: list[dict] = []
    review_seq = 0

    for txn in transactions:
        if rng.random() >= config.review_rate:
            continue

        review_seq += 1
        purchase_date = datetime.strptime(txn["purchase_date"], "%Y-%m-%d %H:%M:%S")
        review_date = purchase_date + timedelta(days=rng.randint(1, 60))

        reviews.append({
            "review_id": f"REV{review_seq:06d}",
            "transaction_id": txn["transaction_id"],
            "customer_id": txn["customer_id"],
            "product_id": txn["product_id"],
            "rating": rng.choices(ratings, weights=rating_weights, k=1)[0],
            "review_date": review_date.strftime("%Y-%m-%d %H:%M:%S"),
            "verified_purchase": True,
        })

    return reviews


def generate_inventory_snapshots(
    products: Sequence[Product],
    transactions: list[dict],
    config: GeneratorConfig,
    rng: random.Random,
) -> list[dict]:
    """Generate daily inventory snapshots for each product.

    Returns plain dicts.  Use the ``InventorySnapshot`` model for schema docs.
    """
    total_days = (config.end_date - config.start_date).days + 1

    # Pre-aggregate units sold per product per day
    daily_sales: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for txn in transactions:
        purchase_date = datetime.strptime(txn["purchase_date"], "%Y-%m-%d %H:%M:%S")
        day_offset = (purchase_date - config.start_date).days
        daily_sales[txn["product_id"]][day_offset] += txn["quantity"]

    snapshots: list[dict] = []
    for product in products:
        stock = int(200 + product.popularity * 300)
        reorder_point = int(stock * 0.25)
        reorder_qty = int(stock * 0.6)

        for day_offset in range(total_days):
            date = config.start_date + timedelta(days=day_offset)
            sold = daily_sales[product.id].get(day_offset, 0)

            received = 0
            if stock < reorder_point:
                received = reorder_qty + rng.randint(-20, 20)
                stock += received

            actual_sold = min(sold, stock)
            stock -= actual_sold

            if stock <= 0:
                status = "out_of_stock"
            elif stock < reorder_point:
                status = "low_stock"
            else:
                status = "in_stock"

            snapshots.append({
                "snapshot_date": date.strftime("%Y-%m-%d"),
                "product_id": product.id,
                "stock_level": stock,
                "units_sold": actual_sold,
                "units_received": received,
                "stock_status": status,
            })

    return snapshots


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------


def write_csv(
    records: Sequence[BaseModel] | Sequence[dict],
    filepath: Path,
) -> None:
    """Write records to a CSV file.

    Accepts either Pydantic model instances or plain dicts.
    """
    if not records:
        print(f"  Skipping {filepath.name} (no records)")
        return

    first = records[0]
    if isinstance(first, BaseModel):
        rows: Sequence[dict] = [r.model_dump() for r in records]  # type: ignore[union-attr]
    else:
        rows = records  # type: ignore[assignment]

    fieldnames = list(rows[0].keys())
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  {filepath.name}: {len(records):,} rows")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_sample(
    records: list[dict],
    model: type[BaseModel],
    label: str,
    rng: random.Random,
    sample_size: int = 500,
) -> None:
    """Validate a random sample of dicts against a Pydantic model."""
    sample = rng.sample(records, min(sample_size, len(records)))
    for record in sample:
        model.model_validate(record)
    print(f"  {label}: validated {len(sample)} sample records")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def verify_csvs(config: GeneratorConfig) -> bool:
    """Verify existing CSV files in the output directory.

    Checks file existence, row counts, Pydantic schema validation on a sample
    of rows, and foreign key integrity between transactions and the product
    catalog.  Returns ``True`` if all checks pass.
    """
    ok = True

    if config.expanded:
        products, _ = generate_expanded_catalog(seed=config.seed)
    else:
        products = list(PRODUCTS)

    product_ids = {p.id for p in products}

    csv_schemas: list[tuple[str, type[BaseModel] | None]] = [
        ("transactions.csv", Transaction),
        ("customers.csv", Customer),
        ("reviews.csv", Review),
        ("inventory_snapshots.csv", InventorySnapshot),
        ("stores.csv", Store),
        ("knowledge_articles.csv", KnowledgeArticle),
        ("support_tickets.csv", SupportTicket),
        ("product_reviews.csv", ProductReview),
    ]

    print(f"Verifying CSVs in {config.output_dir}/\n")
    print(f"  Product catalog: {len(products)} products ({'expanded' if config.expanded else 'original'})\n")

    rng = random.Random(config.seed)

    for filename, model in csv_schemas:
        filepath = config.output_dir / filename
        if not filepath.exists():
            print(f"  MISSING  {filename}")
            ok = False
            continue

        with open(filepath) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        size_mb = filepath.stat().st_size / (1024 * 1024)
        print(f"  {filename}: {len(rows):,} rows ({size_mb:.1f} MB)")

        # Schema validation on a sample
        if model is not None and rows:
            sample = rng.sample(rows, min(500, len(rows)))
            try:
                for row in sample:
                    model.model_validate(row)
                print(f"    schema: OK ({len(sample)} sample rows validated)")
            except Exception as e:
                print(f"    schema: FAIL — {e}")
                ok = False

    # Foreign key check: transaction product_ids vs catalog
    txn_path = config.output_dir / "transactions.csv"
    if txn_path.exists():
        with open(txn_path) as f:
            txn_product_ids = {row["product_id"] for row in csv.DictReader(f)}

        orphans = txn_product_ids - product_ids
        missing = product_ids - txn_product_ids

        print(f"\n  FK integrity:")
        print(f"    Unique product IDs in transactions: {len(txn_product_ids)}")
        if orphans:
            print(f"    FAIL: {len(orphans)} orphan product IDs not in catalog")
            ok = False
        else:
            print(f"    OK: all transaction product_ids exist in catalog")

        if missing:
            print(f"    Note: {len(missing)} catalog products have no transactions")

    if ok:
        print("\n  All checks passed.")
    else:
        print("\n  Some checks FAILED.")

    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate retail transaction dataset")
    parser.add_argument("--expanded", action="store_true", help="Use expanded 500+ product catalog")
    parser.add_argument("--verify", action="store_true", help="Verify existing CSVs without regenerating")
    args = parser.parse_args()

    config = GeneratorConfig(expanded=args.expanded)

    if args.verify:
        ok = verify_csvs(config)
        raise SystemExit(0 if ok else 1)

    rng = random.Random(config.seed)

    if config.expanded:
        products, categories = generate_expanded_catalog(seed=config.seed)
    else:
        products, categories = PRODUCTS, CATEGORIES

    print(f"Output directory: {config.output_dir}")
    config.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nProduct catalog: {len(products)} products across {len(categories)} categories")
    for cat in categories:
        count = sum(1 for p in products if p.category == cat)
        print(f"  {cat}: {count} products")

    print(f"\nGenerating {config.num_customers:,} customers...")
    customers = generate_customers(config, rng)
    write_csv(customers, config.output_dir / "customers.csv")

    print(f"\nGenerating {config.num_stores} stores...")
    stores = generate_stores(config, rng)
    write_csv(stores, config.output_dir / "stores.csv")

    print(f"\nGenerating {config.num_orders:,} orders...")
    transactions = generate_transactions(products, customers, stores, config, rng)
    write_csv(transactions, config.output_dir / "transactions.csv")

    print(f"\nGenerating reviews (~{config.review_rate:.0%} of line items)...")
    reviews = generate_reviews(transactions, config, rng)
    write_csv(reviews, config.output_dir / "reviews.csv")

    print("\nGenerating inventory snapshots...")
    snapshots = generate_inventory_snapshots(products, transactions, config, rng)
    write_csv(snapshots, config.output_dir / "inventory_snapshots.csv")

    print("\nWriting knowledge articles...")
    write_csv(KNOWLEDGE_ARTICLES, config.output_dir / "knowledge_articles.csv")

    print("\nWriting support tickets...")
    write_csv(SUPPORT_TICKETS, config.output_dir / "support_tickets.csv")

    print("\nWriting product reviews...")
    write_csv(PRODUCT_REVIEWS, config.output_dir / "product_reviews.csv")

    # Validate a sample of high-volume records against their Pydantic schemas
    print("\nValidating samples...")
    validation_rng = random.Random(config.seed)
    _validate_sample(transactions, Transaction, "transactions", validation_rng)
    _validate_sample(reviews, Review, "reviews", validation_rng)
    _validate_sample(snapshots, InventorySnapshot, "inventory_snapshots", validation_rng)

    # Verify foreign key integrity
    product_ids = {p.id for p in products}
    txn_product_ids = {t["product_id"] for t in transactions}
    orphan_ids = txn_product_ids - product_ids
    if orphan_ids:
        print(f"\n  WARNING: {len(orphan_ids)} orphan product IDs in transactions!")
    else:
        print(f"\n  FK check: all transaction product_ids exist in catalog")

    print(f"\nDone!")
    print(f"  Orders: {config.num_orders:,}")
    print(f"  Line items (transactions.csv): {len(transactions):,}")
    print(f"  Customers: {len(customers):,}")
    print(f"  Reviews: {len(reviews):,}")
    print(f"  Inventory snapshots: {len(snapshots):,}")
    print(f"  Stores: {len(stores)}")
    print(f"  Knowledge articles: {len(KNOWLEDGE_ARTICLES)}")
    print(f"  Support tickets: {len(SUPPORT_TICKETS)}")
    print(f"  Product reviews: {len(PRODUCT_REVIEWS)}")


if __name__ == "__main__":
    main()
