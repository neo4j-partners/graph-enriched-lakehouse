"""Product catalog constants for the Agentic Commerce assistant.

This module holds the product data, categories, bought-together pairs, and shared
attributes as plain Python data structures with no side-effects on import.  Both
load_products.py (Neo4j loader) and generate_transactions.py (lakehouse data
generator) import from here.
"""

import random
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "BOUGHT_TOGETHER",
    "CATEGORIES",
    "EXPANDED_CATEGORIES",
    "Product",
    "PRODUCTS",
    "SHARED_ATTRIBUTES",
    "generate_expanded_catalog",
]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class Product(BaseModel):
    """A product in the retail catalog."""

    id: str
    name: str
    description: str
    price: float = Field(ge=0)
    category: str
    brand: str
    in_stock: bool = True
    inventory: int = Field(ge=0, default=0)
    popularity: float = Field(ge=0, le=1, default=0.5)
    style: str = ""
    image_url: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)


class SubcategoryDef(BaseModel):
    """Price range and style options for a product subcategory."""

    price_range: tuple[float, float]
    styles: list[str]


type AttributeGenerator = Callable[[random.Random, str], dict[str, Any]]


class CategoryDefinition(BaseModel):
    """Definition for programmatic product generation within a category."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    subcategories: dict[str, SubcategoryDef]
    brands: list[str]
    models: list[str]
    generate_attributes: AttributeGenerator


# ---------------------------------------------------------------------------
# Original product catalog (21 products)
# ---------------------------------------------------------------------------

PRODUCTS: list[Product] = [
    # Running Shoes
    Product(
        id="nike-pegasus-40",
        name="Nike Pegasus 40",
        description="Versatile everyday running shoe with responsive React foam cushioning. Great for road running and daily training.",
        price=130.00,
        category="Running Shoes",
        brand="Nike",
        in_stock=True,
        inventory=45,
        popularity=0.95,
        style="athletic",
        attributes={"cushion": "medium", "weight": "272g", "drop": "10mm", "surface": "road"},
    ),
    Product(
        id="adidas-ultraboost-24",
        name="Adidas Ultraboost 24",
        description="Premium running shoe with Boost midsole for energy return. Primeknit upper for adaptive fit.",
        price=190.00,
        category="Running Shoes",
        brand="Adidas",
        in_stock=True,
        inventory=30,
        popularity=0.90,
        style="athletic",
        attributes={"cushion": "high", "weight": "310g", "drop": "10mm", "surface": "road"},
    ),
    Product(
        id="nb-990v6",
        name="New Balance 990v6",
        description="Heritage running shoe combining classic style with modern performance. Made in USA with premium materials.",
        price=200.00,
        category="Running Shoes",
        brand="New Balance",
        in_stock=True,
        inventory=20,
        popularity=0.85,
        style="classic",
        attributes={"cushion": "medium", "weight": "340g", "drop": "12mm", "surface": "road"},
    ),
    Product(
        id="asics-gel-nimbus-26",
        name="ASICS Gel-Nimbus 26",
        description="Maximum cushion neutral running shoe with FF Blast Plus cushioning and PureGEL technology.",
        price=160.00,
        category="Running Shoes",
        brand="ASICS",
        in_stock=True,
        inventory=35,
        popularity=0.80,
        style="athletic",
        attributes={"cushion": "high", "weight": "290g", "drop": "8mm", "surface": "road"},
    ),
    Product(
        id="brooks-ghost-16",
        name="Brooks Ghost 16",
        description="Smooth and balanced neutral running shoe with DNA Loft v2 cushioning for a soft, smooth ride.",
        price=140.00,
        category="Running Shoes",
        brand="Brooks",
        in_stock=True,
        inventory=40,
        popularity=0.82,
        style="athletic",
        attributes={"cushion": "medium", "weight": "280g", "drop": "12mm", "surface": "road"},
    ),
    # Casual Shoes
    Product(
        id="nike-air-max-90",
        name="Nike Air Max 90",
        description="Iconic lifestyle sneaker with visible Air cushioning. A timeless streetwear classic.",
        price=130.00,
        category="Casual Shoes",
        brand="Nike",
        in_stock=True,
        inventory=50,
        popularity=0.92,
        style="streetwear",
        attributes={"cushion": "medium", "weight": "340g", "occasion": "casual"},
    ),
    Product(
        id="adidas-stan-smith",
        name="Adidas Stan Smith",
        description="Minimalist leather tennis shoe turned everyday classic. Clean white design with green heel tab.",
        price=100.00,
        category="Casual Shoes",
        brand="Adidas",
        in_stock=True,
        inventory=60,
        popularity=0.88,
        style="minimalist",
        attributes={"material": "leather", "occasion": "casual", "closure": "lace"},
    ),
    Product(
        id="nb-574",
        name="New Balance 574",
        description="Classic retro sneaker with ENCAP midsole cushioning. Versatile design for everyday wear.",
        price=90.00,
        category="Casual Shoes",
        brand="New Balance",
        in_stock=True,
        inventory=55,
        popularity=0.84,
        style="retro",
        attributes={"cushion": "medium", "material": "suede/mesh", "occasion": "casual"},
    ),
    # Apparel
    Product(
        id="nike-drifit-tee",
        name="Nike Dri-FIT Running Shirt",
        description="Lightweight moisture-wicking running shirt with Dri-FIT technology. Keeps you dry during intense workouts.",
        price=35.00,
        category="Apparel",
        brand="Nike",
        in_stock=True,
        inventory=100,
        popularity=0.75,
        style="athletic",
        attributes={"material": "polyester", "fit": "standard", "technology": "Dri-FIT"},
    ),
    Product(
        id="adidas-running-shorts",
        name="Adidas Running Shorts",
        description="Lightweight running shorts with built-in brief liner. AEROREADY moisture management for comfort.",
        price=30.00,
        category="Apparel",
        brand="Adidas",
        in_stock=True,
        inventory=80,
        popularity=0.70,
        style="athletic",
        attributes={"material": "recycled polyester", "fit": "regular", "inseam": "5 inch"},
    ),
    Product(
        id="ua-coldgear",
        name="Under Armour ColdGear Base Layer",
        description="Warm base layer for cold-weather running. Dual-layer fabric traps heat without bulk.",
        price=55.00,
        category="Apparel",
        brand="Under Armour",
        in_stock=True,
        inventory=40,
        popularity=0.72,
        style="athletic",
        attributes={"material": "polyester/elastane", "fit": "compression", "technology": "ColdGear"},
    ),
    # Accessories
    Product(
        id="garmin-forerunner-265",
        name="Garmin Forerunner 265",
        description="GPS running smartwatch with AMOLED display. Tracks pace, heart rate, training status, and recovery.",
        price=450.00,
        category="Outdoor Equipment",
        brand="Garmin",
        in_stock=True,
        inventory=15,
        popularity=0.88,
        style="tech",
        attributes={"battery_life": "13 days", "gps": "multi-band", "display": "AMOLED"},
    ),
    Product(
        id="nike-running-socks",
        name="Nike Multiplier Running Socks (2-Pack)",
        description="Cushioned running socks with Dri-FIT moisture wicking. Arch band support and reinforced heel and toe.",
        price=18.00,
        category="Accessories",
        brand="Nike",
        in_stock=True,
        inventory=200,
        popularity=0.65,
        style="athletic",
        attributes={"material": "polyester blend", "cushion": "medium", "pack_size": "2"},
    ),
    Product(
        id="hydration-belt",
        name="Nathan Trail Mix Plus Hydration Belt",
        description="Adjustable hydration belt with two 10oz flasks. Zippered pocket for phone and essentials.",
        price=40.00,
        category="Accessories",
        brand="Nathan",
        in_stock=False,
        inventory=0,
        popularity=0.60,
        style="athletic",
        attributes={"capacity": "20oz", "pockets": "1 zippered", "bottles": "2"},
    ),
    # Equipment
    Product(
        id="foam-roller",
        name="TriggerPoint GRID Foam Roller",
        description="Multi-density foam roller for muscle recovery and self-massage. Patented GRID surface for targeted relief.",
        price=35.00,
        category="Equipment",
        brand="TriggerPoint",
        in_stock=True,
        inventory=25,
        popularity=0.68,
        style="recovery",
        attributes={"length": "13 inch", "density": "multi", "material": "EVA foam"},
    ),
    Product(
        id="resistance-bands",
        name="Theraband Resistance Bands Set",
        description="Set of 5 resistance bands for strength training and injury prevention. Progressive resistance levels.",
        price=25.00,
        category="Equipment",
        brand="Theraband",
        in_stock=True,
        inventory=50,
        popularity=0.62,
        style="training",
        attributes={"pieces": "5", "resistance_levels": "light to heavy", "material": "latex"},
    ),
    # Outdoor Equipment
    Product(
        id="rei-half-dome-tent",
        name="REI Co-op Half Dome SL 2+ Tent",
        description="Lightweight 2-person backpacking tent with color-coded setup and full rainfly. Great balance of weight and livability.",
        price=279.00,
        category="Outdoor Equipment",
        brand="REI Co-op",
        in_stock=True,
        inventory=20,
        popularity=0.85,
        style="outdoor",
        attributes={"capacity": "2-person", "weight": "1.64kg", "seasons": "3-season", "setup": "freestanding"},
    ),
    Product(
        id="nemo-disco-sleeping-bag",
        name="NEMO Disco 30 Sleeping Bag",
        description="Spoon-shaped sleeping bag with 30°F rating. Extra room at knees and elbows for side sleepers.",
        price=219.95,
        category="Outdoor Equipment",
        brand="NEMO",
        in_stock=True,
        inventory=25,
        popularity=0.80,
        style="outdoor",
        attributes={"temp_rating": "30°F", "fill": "synthetic", "shape": "spoon", "weight": "1.13kg"},
    ),
    Product(
        id="msr-hubba-hubba-tent",
        name="MSR Hubba Hubba NX 2 Tent",
        description="Award-winning ultralight 2-person backpacking tent. Symmetrical design with two doors and two vestibules.",
        price=450.00,
        category="Outdoor Equipment",
        brand="MSR",
        in_stock=True,
        inventory=12,
        popularity=0.90,
        style="outdoor",
        attributes={"capacity": "2-person", "weight": "1.54kg", "seasons": "3-season", "setup": "freestanding"},
    ),
    Product(
        id="kelty-cosmic-sleeping-bag",
        name="Kelty Cosmic 20 Down Sleeping Bag",
        description="Affordable 20°F down sleeping bag with 550-fill DriDown insulation. Great value for backpacking.",
        price=129.95,
        category="Outdoor Equipment",
        brand="Kelty",
        in_stock=True,
        inventory=35,
        popularity=0.75,
        style="outdoor",
        attributes={"temp_rating": "20°F", "fill": "550-fill down", "shape": "mummy", "weight": "1.36kg"},
    ),
    Product(
        id="therm-a-rest-sleeping-pad",
        name="Therm-a-Rest NeoAir XTherm Sleeping Pad",
        description="Ultralight 4-season inflatable sleeping pad with R-value of 6.9. Premium warmth-to-weight ratio.",
        price=229.95,
        category="Outdoor Equipment",
        brand="Therm-a-Rest",
        in_stock=True,
        inventory=18,
        popularity=0.82,
        style="outdoor",
        attributes={"r_value": "6.9", "weight": "430g", "thickness": "6.4cm", "seasons": "4-season"},
    ),
]

# ---------------------------------------------------------------------------
# Categories with descriptions
# ---------------------------------------------------------------------------

CATEGORIES: dict[str, str] = {
    "Running Shoes": "Performance footwear designed for running and jogging",
    "Casual Shoes": "Everyday lifestyle footwear for casual wear",
    "Apparel": "Athletic clothing for running and training",
    "Accessories": "Watches, socks, hydration, and other running accessories",
    "Equipment": "Recovery and training equipment for runners",
    "Outdoor Equipment": "Tents, sleeping bags, GPS devices, and gear for outdoor adventures",
}

# ---------------------------------------------------------------------------
# Manually defined "bought together" pairs
# (product_id_1, product_id_2, frequency, confidence)
# ---------------------------------------------------------------------------

BOUGHT_TOGETHER: list[tuple[str, str, int, float]] = [
    ("nike-pegasus-40", "nike-running-socks", 85, 0.72),
    ("nike-pegasus-40", "nike-drifit-tee", 60, 0.55),
    ("adidas-ultraboost-24", "adidas-running-shorts", 50, 0.48),
    ("brooks-ghost-16", "hydration-belt", 30, 0.35),
    ("garmin-forerunner-265", "nike-pegasus-40", 40, 0.42),
    ("foam-roller", "resistance-bands", 55, 0.60),
    ("nike-air-max-90", "adidas-stan-smith", 20, 0.15),
    ("ua-coldgear", "nike-running-socks", 35, 0.38),
    # Outdoor Equipment pairs
    ("rei-half-dome-tent", "nemo-disco-sleeping-bag", 45, 0.52),
    ("rei-half-dome-tent", "therm-a-rest-sleeping-pad", 40, 0.48),
    ("msr-hubba-hubba-tent", "kelty-cosmic-sleeping-bag", 35, 0.40),
    ("msr-hubba-hubba-tent", "therm-a-rest-sleeping-pad", 38, 0.45),
    ("nemo-disco-sleeping-bag", "therm-a-rest-sleeping-pad", 50, 0.55),
    ("kelty-cosmic-sleeping-bag", "therm-a-rest-sleeping-pad", 42, 0.50),
    ("garmin-forerunner-265", "rei-half-dome-tent", 15, 0.12),
]

# ---------------------------------------------------------------------------
# Attribute nodes to create (name, value pairs shared across products)
# ---------------------------------------------------------------------------

SHARED_ATTRIBUTES: list[tuple[str, str]] = [
    ("Cushion Level", "medium"),
    ("Cushion Level", "high"),
    ("Surface", "road"),
    ("Occasion", "casual"),
    ("Fit", "standard"),
    ("Fit", "compression"),
    ("Material", "polyester"),
    # Outdoor Equipment attributes
    ("Seasons", "3-season"),
    ("Seasons", "4-season"),
    ("Fill", "synthetic"),
    ("Fill", "down"),
    ("Setup", "freestanding"),
]


# ---------------------------------------------------------------------------
# Expanded catalog generation (500+ products)
# ---------------------------------------------------------------------------

# Attribute generator functions per category

def _running_shoe_attrs(rng: random.Random, subcat: str) -> dict[str, Any]:
    return {
        "cushion": rng.choice(["low", "medium", "high"]),
        "weight": f"{rng.randint(180, 340)}g",
        "drop": f"{rng.choice([0, 4, 6, 8, 10, 12])}mm",
        "surface": "trail" if "Trail" in subcat else "road",
    }


def _casual_shoe_attrs(rng: random.Random, subcat: str) -> dict[str, Any]:
    return {
        "material": rng.choice(["leather", "canvas", "suede", "synthetic", "mesh"]),
        "occasion": "casual",
    }


def _apparel_attrs(rng: random.Random, subcat: str) -> dict[str, Any]:
    return {
        "material": rng.choice(["polyester", "recycled polyester", "nylon", "merino wool", "polyester/elastane"]),
        "fit": rng.choice(["standard", "slim", "relaxed", "compression"]),
    }


def _accessory_attrs(rng: random.Random, subcat: str) -> dict[str, Any]:
    if "Watch" in subcat:
        return {
            "battery_life": f"{rng.randint(5, 21)} days",
            "gps": rng.choice(["multi-band", "standard"]),
            "display": rng.choice(["AMOLED", "MIP", "LCD"]),
        }
    if "Sock" in subcat:
        return {
            "material": "polyester blend",
            "cushion": rng.choice(["light", "medium", "heavy"]),
        }
    return {"material": rng.choice(["nylon", "polyester", "polycarbonate"])}


def _equipment_attrs(rng: random.Random, subcat: str) -> dict[str, Any]:
    return {"material": rng.choice(["EVA foam", "rubber", "TPE", "steel", "nylon"])}


def _nutrition_attrs(rng: random.Random, subcat: str) -> dict[str, Any]:
    return {"serving_size": rng.choice(["1 packet", "1 scoop", "1 tablet", "1 bar"])}


def _outdoor_attrs(rng: random.Random, subcat: str) -> dict[str, Any]:
    if "Boot" in subcat:
        return {
            "waterproof": rng.choice([True, False]),
            "weight": f"{rng.randint(400, 900)}g",
        }
    if "Backpack" in subcat:
        return {"capacity": f"{rng.choice([15, 20, 25, 30, 40, 50])}L"}
    return {"material": rng.choice(["Gore-Tex", "nylon", "ripstop", "polyester"])}


# Category / subcategory / brand matrix with price ranges.
# generate_attributes is a direct Callable reference (no string dispatch).
EXPANDED_CATEGORY_DEFS: dict[str, CategoryDefinition] = {
    "Running Shoes": CategoryDefinition(
        subcategories={
            "Road Running": SubcategoryDef(price_range=(100, 250), styles=["athletic"]),
            "Trail Running": SubcategoryDef(price_range=(110, 230), styles=["athletic", "outdoor"]),
            "Racing Flats": SubcategoryDef(price_range=(130, 280), styles=["athletic"]),
            "Stability": SubcategoryDef(price_range=(120, 220), styles=["athletic"]),
            "Motion Control": SubcategoryDef(price_range=(130, 200), styles=["athletic"]),
        },
        brands=["Nike", "Adidas", "New Balance", "ASICS", "Brooks", "Hoka", "Saucony", "On"],
        models=["Racer", "Glide", "Swift", "Tempo", "Aero", "Dash", "Stride", "Velocity", "Pulse", "Sprint"],
        generate_attributes=_running_shoe_attrs,
    ),
    "Casual Shoes": CategoryDefinition(
        subcategories={
            "Sneakers": SubcategoryDef(price_range=(60, 180), styles=["streetwear", "minimalist"]),
            "Sandals": SubcategoryDef(price_range=(30, 100), styles=["casual"]),
            "Boots": SubcategoryDef(price_range=(90, 250), styles=["classic", "streetwear"]),
            "Slip-ons": SubcategoryDef(price_range=(50, 140), styles=["minimalist", "casual"]),
        },
        brands=["Nike", "Adidas", "New Balance", "Vans", "Converse", "Puma"],
        models=["Classic", "Retro", "Urban", "Metro", "Core", "Flex", "Step", "Wave"],
        generate_attributes=_casual_shoe_attrs,
    ),
    "Apparel": CategoryDefinition(
        subcategories={
            "Tops": SubcategoryDef(price_range=(25, 80), styles=["athletic"]),
            "Bottoms": SubcategoryDef(price_range=(30, 90), styles=["athletic"]),
            "Jackets": SubcategoryDef(price_range=(60, 200), styles=["athletic", "outdoor"]),
            "Base Layers": SubcategoryDef(price_range=(35, 100), styles=["athletic"]),
            "Compression": SubcategoryDef(price_range=(40, 90), styles=["athletic"]),
        },
        brands=["Nike", "Adidas", "Under Armour", "New Balance", "Puma", "Brooks", "ASICS", "Hoka"],
        models=["Pro", "Elite", "Lite", "Shield", "Vent", "Move", "Active", "Zone"],
        generate_attributes=_apparel_attrs,
    ),
    "Accessories": CategoryDefinition(
        subcategories={
            "Watches": SubcategoryDef(price_range=(150, 600), styles=["tech"]),
            "Socks": SubcategoryDef(price_range=(12, 30), styles=["athletic"]),
            "Hydration": SubcategoryDef(price_range=(15, 80), styles=["athletic"]),
            "Bags": SubcategoryDef(price_range=(30, 120), styles=["athletic", "casual"]),
            "Sunglasses": SubcategoryDef(price_range=(80, 250), styles=["athletic", "casual"]),
            "Headbands": SubcategoryDef(price_range=(10, 30), styles=["athletic"]),
        },
        brands=["Garmin", "Coros", "Nike", "Adidas", "Nathan", "Oakley", "Goodr", "Polar"],
        models=["Sport", "Ultra", "Trail", "Race", "Pace", "Edge", "Peak", "Run"],
        generate_attributes=_accessory_attrs,
    ),
    "Equipment": CategoryDefinition(
        subcategories={
            "Recovery": SubcategoryDef(price_range=(20, 120), styles=["recovery"]),
            "Strength": SubcategoryDef(price_range=(15, 80), styles=["training"]),
            "Yoga": SubcategoryDef(price_range=(20, 100), styles=["training"]),
            "Cardio": SubcategoryDef(price_range=(25, 150), styles=["training"]),
        },
        brands=["TriggerPoint", "Theraband", "Hyperice", "Manduka", "TRX", "Rogue"],
        models=["Pro", "Core", "Max", "Flex", "Flow", "Force"],
        generate_attributes=_equipment_attrs,
    ),
    "Nutrition": CategoryDefinition(
        subcategories={
            "Energy Gels": SubcategoryDef(price_range=(2, 5), styles=["nutrition"]),
            "Protein": SubcategoryDef(price_range=(25, 60), styles=["nutrition"]),
            "Electrolytes": SubcategoryDef(price_range=(15, 40), styles=["nutrition"]),
            "Bars": SubcategoryDef(price_range=(2, 5), styles=["nutrition"]),
        },
        brands=["GU", "Clif", "Nuun", "Tailwind", "Skratch Labs", "Maurten"],
        models=["Energy", "Endurance", "Recovery", "Hydra", "Fuel", "Boost"],
        generate_attributes=_nutrition_attrs,
    ),
    "Outdoor": CategoryDefinition(
        subcategories={
            "Hiking Boots": SubcategoryDef(price_range=(100, 300), styles=["outdoor"]),
            "Backpacks": SubcategoryDef(price_range=(50, 250), styles=["outdoor"]),
            "Trekking Poles": SubcategoryDef(price_range=(40, 180), styles=["outdoor"]),
            "Rain Gear": SubcategoryDef(price_range=(60, 300), styles=["outdoor"]),
        },
        brands=["Salomon", "Merrell", "The North Face", "Patagonia", "Arc'teryx", "Columbia"],
        models=["Summit", "Trail", "Peak", "Ridge", "Alpine", "Venture", "Explorer", "Trek"],
        generate_attributes=_outdoor_attrs,
    ),
}

EXPANDED_CATEGORIES: dict[str, str] = {
    **CATEGORIES,
    "Nutrition": "Energy gels, protein, electrolytes, and bars for athletic performance",
    "Outdoor": "Hiking boots, backpacks, trekking poles, and rain gear for outdoor activities",
    "Outdoor Equipment": "Tents, sleeping bags, GPS devices, and gear for outdoor adventures",
}

# Description templates per category
_DESCRIPTION_TEMPLATES: dict[str, list[str]] = {
    "Running Shoes": [
        "{brand} {name} {subcat} shoe built for {style} performance. Responsive cushioning and lightweight design.",
        "High-performance {subcat} shoe from {brand}. The {name} delivers comfort and speed for every run.",
        "{brand}'s {name} — a versatile {subcat} shoe with modern cushioning technology and a secure fit.",
    ],
    "Casual Shoes": [
        "{brand} {name} {subcat} for everyday style. Comfortable design meets classic aesthetics.",
        "The {brand} {name} — a modern {subcat} that transitions seamlessly from street to social.",
        "Versatile {brand} {name} {subcat} with premium materials and all-day comfort.",
    ],
    "Apparel": [
        "{brand} {name} {subcat} with moisture-wicking technology. Designed for performance and comfort.",
        "Lightweight {brand} {name} {subcat} engineered for athletes. Breathable and flexible construction.",
        "{brand}'s {name} {subcat} — high-performance athletic wear with a modern fit.",
    ],
    "Accessories": [
        "{brand} {name} {subcat} for runners and athletes. Built for durability and performance.",
        "The {brand} {name} — a premium {subcat} accessory designed for serious athletes.",
        "{brand} {name} {subcat} with advanced features for training and racing.",
    ],
    "Equipment": [
        "{brand} {name} {subcat} equipment for training and recovery. Professional-grade design.",
        "The {brand} {name} — {subcat} gear built for athletes who demand the best.",
        "{brand} {name} {subcat} equipment with innovative design for optimal results.",
    ],
    "Nutrition": [
        "{brand} {name} {subcat} for sustained energy and performance. Science-backed formula.",
        "The {brand} {name} — premium {subcat} designed for endurance athletes.",
        "{brand} {name} {subcat} with clean ingredients for peak athletic performance.",
    ],
    "Outdoor": [
        "{brand} {name} {subcat} built for the trail. Durable construction meets outdoor performance.",
        "The {brand} {name} — premium {subcat} for serious outdoor adventurers.",
        "{brand} {name} {subcat} with weather-resistant materials and rugged durability.",
    ],
}


def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    return text.lower().replace(" ", "-").replace("'", "").replace(".", "")


def generate_expanded_catalog(seed: int = 42) -> tuple[list[Product], dict[str, str]]:
    """Generate 500+ products across 7 categories and 40+ brands.

    Returns ``(products, categories)`` where *products* keeps the original 16
    products at the start of the list for stable demo ordering.
    """
    rng = random.Random(seed)

    existing_ids: set[str] = {p.id for p in PRODUCTS}
    expanded: list[Product] = list(PRODUCTS)

    for cat_name, cat_def in EXPANDED_CATEGORY_DEFS.items():
        templates = _DESCRIPTION_TEMPLATES[cat_name]

        for subcat_name, subcat_def in cat_def.subcategories.items():
            price_lo, price_hi = subcat_def.price_range

            for brand in cat_def.brands:
                num_products = rng.choices([2, 3], weights=[60, 40], k=1)[0]

                for _ in range(num_products):
                    model = rng.choice(cat_def.models)
                    version = rng.choice(["", " 2", " 3", " Pro", " Elite", " Lite", " Plus"])
                    product_name = f"{brand} {model} {subcat_name}{version}".strip()

                    pid = _slugify(product_name)
                    if pid in existing_ids:
                        pid = f"{pid}-{rng.randint(100, 999)}"
                    if pid in existing_ids:
                        continue
                    existing_ids.add(pid)

                    style = rng.choice(subcat_def.styles)
                    template = rng.choice(templates)
                    description = template.format(
                        brand=brand,
                        name=f"{model}{version}".strip(),
                        subcat=subcat_name.lower(),
                        style=style,
                    )
                    inventory = rng.randint(0, 200)

                    expanded.append(
                        Product(
                            id=pid,
                            name=product_name,
                            description=description,
                            price=round(rng.uniform(price_lo, price_hi), 2),
                            category=cat_name,
                            brand=brand,
                            in_stock=inventory > 0,
                            inventory=inventory,
                            popularity=round(rng.uniform(0.3, 0.98), 2),
                            style=style,
                            attributes=cat_def.generate_attributes(rng, subcat_name),
                        )
                    )

    return expanded, EXPANDED_CATEGORIES
