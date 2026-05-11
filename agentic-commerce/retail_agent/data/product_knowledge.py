"""Knowledge articles, support tickets, and reviews for the 21 base products.

This module provides product-specific troubleshooting guides, manuals, FAQs,
customer support ticket data, and reviews for use in the Graph RAG knowledge
base.  Both load scripts and the Databricks agent can import from here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from retail_agent.data.product_catalog import PRODUCTS

__all__ = [
    "KnowledgeArticle",
    "KNOWLEDGE_ARTICLES",
    "Review",
    "REVIEWS",
    "SupportTicket",
    "SUPPORT_TICKETS",
]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class KnowledgeArticle(BaseModel):
    """A knowledge-base article for a product."""

    article_id: str
    product_id: str
    document_type: Literal["Troubleshooting", "Manual", "FAQ"]
    title: str
    content: str


class SupportTicket(BaseModel):
    """A customer support ticket for a product."""

    ticket_id: str
    product_id: str
    status: Literal["Open", "Closed"]
    issue_description: str
    resolution_text: str


class Review(BaseModel):
    """A customer review for a product."""

    review_id: str
    product_id: str
    rating: int = Field(ge=1, le=5)
    date: str
    raw_text: str


# ---------------------------------------------------------------------------
# Valid product IDs (for runtime validation)
# ---------------------------------------------------------------------------

_VALID_PRODUCT_IDS: set[str] = {p.id for p in PRODUCTS}


# ---------------------------------------------------------------------------
# Knowledge Articles  (84 total — 4 per product)
# ---------------------------------------------------------------------------

KNOWLEDGE_ARTICLES: list[KnowledgeArticle] = [
    # ── nike-pegasus-40 ───────────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-001",
        product_id="nike-pegasus-40",
        document_type="Manual",
        title="Nike Pegasus 40 Break-In Guide",
        content="The Nike Pegasus 40 requires minimal break-in. Wear them for short 2-3 mile runs for the first week to let the React foam midsole adapt to your gait. Avoid long runs or speed work until the upper mesh has loosened slightly.",
    ),
    KnowledgeArticle(
        article_id="KA-002",
        product_id="nike-pegasus-40",
        document_type="FAQ",
        title="Nike Pegasus 40 Sizing",
        content="Q: Do the Pegasus 40 run true to size? A: Yes, they generally run true to size. Customers with wider feet may want to try the wide (2E) option, as the engineered mesh upper fits snugly in the midfoot.",
    ),
    KnowledgeArticle(
        article_id="KA-003",
        product_id="nike-pegasus-40",
        document_type="Troubleshooting",
        title="Cushion Feels Flat After 300 Miles",
        content="Symptom: The React foam midsole feels less responsive and flat after 300+ miles of use. This loss of cushion responsiveness is common across all foam midsole technologies — React (Nike), Boost (Adidas), FF Blast Plus (ASICS), DNA Loft (Brooks), and ENCAP (New Balance) each degrade at different rates depending on runner weight and running surface. Solution: Running shoes should be replaced every 300-500 miles regardless of brand. Check the outsole tread pattern — if worn smooth, it is time for a new pair. Rotating between two pairs of daily trainers extends the life of both by allowing the foam cells to recover between runs.",
    ),
    KnowledgeArticle(
        article_id="KA-004",
        product_id="nike-pegasus-40",
        document_type="Troubleshooting",
        title="Heel Counter Rubbing and Blisters",
        content="Symptom: Irritation or blisters at the back of the heel. Solution: Ensure you are using a heel-lock lacing technique (runner's loop) to prevent heel slippage. If the issue persists, try wearing thicker running socks or apply moleskin to the affected area.",
    ),

    # ── adidas-ultraboost-24 ──────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-005",
        product_id="adidas-ultraboost-24",
        document_type="Manual",
        title="Adidas Ultraboost 24 Care Instructions",
        content="Clean the Primeknit upper with a soft brush and lukewarm water. Do not machine wash — the Boost midsole can deform in high heat. Remove insoles and air dry at room temperature. Avoid direct sunlight to prevent yellowing of the Boost foam.",
    ),
    KnowledgeArticle(
        article_id="KA-006",
        product_id="adidas-ultraboost-24",
        document_type="FAQ",
        title="Ultraboost 24 for Long-Distance Running",
        content="Q: Are the Ultraboost 24 suitable for marathon training? A: Yes. The full-length Boost midsole provides excellent energy return over long distances. The Primeknit upper offers adaptive support. However, at 310g they are heavier than dedicated racing shoes.",
    ),
    KnowledgeArticle(
        article_id="KA-007",
        product_id="adidas-ultraboost-24",
        document_type="Troubleshooting",
        title="Boost Midsole Turning Yellow",
        content="Symptom: The white Boost foam has yellowed over time. Yellowing from UV exposure and oxidation is a common cosmetic issue across shoes with white foam midsoles, including the Nike Air Max 90, Adidas Stan Smith, and New Balance 574. It does not affect performance. Solution: Apply a paste of baking soda and hydrogen peroxide, scrub gently, and leave in indirect sunlight for 2-3 hours. This same cleaning method works on any yellowed foam or rubber midsole. Prevent yellowing by storing shoes away from direct sunlight and applying a UV-protectant spray.",
    ),
    KnowledgeArticle(
        article_id="KA-008",
        product_id="adidas-ultraboost-24",
        document_type="Troubleshooting",
        title="Continental Outsole Peeling",
        content="Symptom: The Continental rubber outsole is separating from the Boost midsole at the toe. Outsole separation is one of the most commonly reported issues across running and lifestyle shoes — it has been reported on models from Nike, ASICS, and Brooks as well, though it is most frequent on the Ultraboost due to the flexible Boost foam. Solution: If within 6 months of purchase, contact Adidas for warranty replacement. For minor separation, a shoe-specific adhesive (e.g., Shoe Goo) can provide a temporary fix. Avoid leaving shoes in hot cars, as heat weakens the adhesive bond between the outsole and midsole.",
    ),

    # ── nb-990v6 ──────────────────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-009",
        product_id="nb-990v6",
        document_type="Manual",
        title="New Balance 990v6 Lacing Guide",
        content="The 990v6 features premium pigskin and mesh uppers. Use the standard criss-cross lacing for a secure fit. For wider feet, skip the bottom eyelet to create more volume in the toe box. The padded collar provides ankle support without requiring tight lacing.",
    ),
    KnowledgeArticle(
        article_id="KA-010",
        product_id="nb-990v6",
        document_type="FAQ",
        title="990v6 Made in USA Details",
        content="Q: Is the 990v6 really made in the USA? A: Yes, the 990v6 is assembled in the USA from domestic and imported materials. The premium construction justifies the higher price point. New Balance commits to at least 70% domestic content by value.",
    ),
    KnowledgeArticle(
        article_id="KA-011",
        product_id="nb-990v6",
        document_type="Troubleshooting",
        title="Suede Staining and Water Marks",
        content="Symptom: Water spots or stains on the pigskin suede panels. Water damage to suede is one of the most common complaints across suede shoes, including the New Balance 574 and any suede-paneled sneaker. Unlike leather (which can be conditioned for water resistance) or synthetic mesh (which dries quickly), suede stains permanently if not treated. Solution: Apply a suede protector spray before first wear — this applies to any suede shoe. For existing stains, use a suede eraser or brush to restore the nap. Let shoes dry naturally at room temperature; never use heat, which can shrink and harden the suede.",
    ),
    KnowledgeArticle(
        article_id="KA-012",
        product_id="nb-990v6",
        document_type="Troubleshooting",
        title="ENCAP Midsole Feels Firm",
        content="Symptom: New 990v6 feels stiff compared to softer foam shoes like the Nike Pegasus (React foam) or Adidas Ultraboost (Boost). Many customers switching from soft-foam running shoes find the ENCAP midsole unexpectedly firm. Solution: The dual-density ENCAP midsole is designed for stability, not maximum cushion — similar to how the Adidas Stan Smith leather requires break-in. Allow 20-30 miles of break-in for the foam to soften. If you prefer a softer ride, consider the FuelCell-based 990v6 SE variant, or pair with a cushioned insole.",
    ),

    # ── asics-gel-nimbus-26 ───────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-013",
        product_id="asics-gel-nimbus-26",
        document_type="Manual",
        title="ASICS Gel-Nimbus 26 First Run Setup",
        content="Remove the cardboard inserts and check that the OrthoLite X-55 insole is seated flat. The FF Blast Plus midsole will feel bouncy out of the box — this is normal. Lace snugly through the midfoot but leave room in the toe box for natural splay.",
    ),
    KnowledgeArticle(
        article_id="KA-014",
        product_id="asics-gel-nimbus-26",
        document_type="FAQ",
        title="Gel-Nimbus 26 vs. Kayano 30",
        content="Q: What is the difference between the Nimbus and Kayano? A: The Nimbus 26 is a neutral shoe for runners who do not overpronate. The Kayano 30 includes a 4D Guidance System for stability. If you need arch support or pronation control, choose the Kayano.",
    ),
    KnowledgeArticle(
        article_id="KA-015",
        product_id="asics-gel-nimbus-26",
        document_type="Troubleshooting",
        title="PureGEL Insert Feels Uneven",
        content="Symptom: A hard lump or uneven surface under the heel. Insole and midsole comfort issues are common across running shoes — the Brooks Ghost 16 can develop squeaking from insole friction, and the New Balance 574 insole can slide out of position. With the Nimbus 26, the issue is specific to the PureGEL insert. Solution: The PureGEL technology is a lightweight silicone-based cushion embedded in the midsole. If it feels uneven, remove the OrthoLite X-55 insole and check for debris underneath. If the midsole itself is deformed, this is a manufacturing defect — contact ASICS for replacement.",
    ),
    KnowledgeArticle(
        article_id="KA-016",
        product_id="asics-gel-nimbus-26",
        document_type="Troubleshooting",
        title="Upper Mesh Tearing at Toe Box",
        content="Symptom: Small tears in the knit mesh near the big toe. Solution: This is often caused by toenails that need trimming or by sizing too small. Ensure at least a thumb's width of space between your longest toe and the end of the shoe. Consider going up a half size.",
    ),

    # ── brooks-ghost-16 ──────────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-017",
        product_id="brooks-ghost-16",
        document_type="Manual",
        title="Brooks Ghost 16 Rotation Recommendations",
        content="The Ghost 16 is ideal as a daily trainer. For a complete rotation, pair it with a lightweight racer for speed days and a trail shoe for off-road. The DNA Loft v2 midsole performs best at easy-to-moderate paces.",
    ),
    KnowledgeArticle(
        article_id="KA-018",
        product_id="brooks-ghost-16",
        document_type="FAQ",
        title="Ghost 16 Arch Support Level",
        content="Q: Does the Ghost 16 have arch support? A: The Ghost 16 is a neutral shoe with no medial post or stability features. It suits runners with normal to high arches. If you need pronation support, consider the Brooks Adrenaline GTS instead.",
    ),
    KnowledgeArticle(
        article_id="KA-019",
        product_id="brooks-ghost-16",
        document_type="Troubleshooting",
        title="Squeaking Noise from Insole",
        content="Symptom: A squeaking sound with every step. Solution: Remove the insole and sprinkle a thin layer of baby powder or cornstarch on top of the midsole before replacing the insole. This eliminates friction between the insole and the midsole surface.",
    ),
    KnowledgeArticle(
        article_id="KA-020",
        product_id="brooks-ghost-16",
        document_type="Troubleshooting",
        title="Outsole Wear on Outer Edge",
        content="Symptom: Excessive wear on the lateral (outer) edge of the outsole, with visible outsole separation beginning at the heel. Outsole wear and separation are among the most reported issues across running shoes — the Adidas Ultraboost Continental outsole and Nike Pegasus outsole have similar reports. With the Ghost 16, the wear pattern specifically indicates supination (underpronation). Solution: The Ghost 16 is a neutral shoe, which is correct for supinators, but the DNA Loft v2 midsole may compress unevenly over time. Replace every 300-400 miles. For outsole separation, Shoe Goo adhesive provides a temporary fix. If significant delamination occurs within 90 days, contact Brooks for warranty assessment.",
    ),

    # ── nike-air-max-90 ──────────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-021",
        product_id="nike-air-max-90",
        document_type="Manual",
        title="Nike Air Max 90 Cleaning Guide",
        content="Use a soft-bristle brush with mild soap and warm water. For the leather panels, use a leather cleaner. For the mesh toe box, scrub gently to avoid fraying. Wipe the visible Air unit with a damp cloth. Air dry away from heat — never use a dryer.",
    ),
    KnowledgeArticle(
        article_id="KA-022",
        product_id="nike-air-max-90",
        document_type="FAQ",
        title="Air Max 90 for Exercise",
        content="Q: Can I run in the Air Max 90? A: The Air Max 90 is designed as a lifestyle sneaker, not a performance running shoe. The visible Air unit provides casual cushioning but lacks the support and responsiveness needed for serious running. Use dedicated running shoes for exercise.",
    ),
    KnowledgeArticle(
        article_id="KA-023",
        product_id="nike-air-max-90",
        document_type="Troubleshooting",
        title="Visible Air Unit Deflating",
        content="Symptom: The Air bubble in the heel appears flat or crinkled. Solution: Over time, the polyurethane Air unit can lose pressure. This is irreversible and indicates the shoe has reached end of life. Nike does not offer Air unit replacements. If it deflates within 2 years of purchase, contact Nike for a warranty claim.",
    ),
    KnowledgeArticle(
        article_id="KA-024",
        product_id="nike-air-max-90",
        document_type="Troubleshooting",
        title="Yellowing of the White Midsole",
        content="Symptom: The white midsole and Air unit have yellowed. Yellowing from UV exposure and oxidation affects any shoe with white foam or rubber — the Adidas Ultraboost Boost midsole, Adidas Stan Smith rubber outsole, and New Balance 574 ENCAP midsole all experience the same cosmetic issue. Solution: Clean with a paste of baking soda and hydrogen peroxide (this same method works across all yellowed midsoles). For the Air Max 90 specifically, apply a thin coat of salon-grade hydrogen peroxide cream, wrap in plastic wrap, and place in sunlight for 3-4 hours. Prevent yellowing by storing shoes away from direct sunlight.",
    ),

    # ── adidas-stan-smith ────────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-025",
        product_id="adidas-stan-smith",
        document_type="Manual",
        title="Adidas Stan Smith Leather Care",
        content="The Stan Smith features a full-grain leather upper. Apply a leather conditioner every 2-3 months to prevent cracking. Use white shoe polish for scuff marks. Store with cedar shoe trees to maintain shape and absorb moisture.",
    ),
    KnowledgeArticle(
        article_id="KA-026",
        product_id="adidas-stan-smith",
        document_type="FAQ",
        title="Stan Smith Break-In Period",
        content="Q: Do the Stan Smiths need breaking in? A: Yes, the full-grain leather upper is stiff initially — this is a different kind of break-in than running shoes like the New Balance 990v6 (which has a firm ENCAP midsole that needs 20-30 miles) or the Under Armour ColdGear compression base layer (which feels very tight at first). For leather shoes, wear them for short periods (1-2 hours) for the first week. The leather will soften and conform to your foot shape. Wearing thick socks during break-in can speed up the process.",
    ),
    KnowledgeArticle(
        article_id="KA-027",
        product_id="adidas-stan-smith",
        document_type="Troubleshooting",
        title="Leather Cracking and Creasing",
        content="Symptom: Deep creases or cracks forming across the toe box. The white rubber midsole may also yellow over time from UV exposure — the same oxidation issue that affects Adidas Ultraboost Boost foam and Nike Air Max 90 midsoles. Solution: For leather cracking, apply a leather conditioner immediately. Creasing is normal but cracking indicates dryness. For deep cracks, use a leather filler followed by white polish. Prevent with regular conditioning and cedar shoe trees. For midsole yellowing, use the baking soda and hydrogen peroxide paste method.",
    ),
    KnowledgeArticle(
        article_id="KA-028",
        product_id="adidas-stan-smith",
        document_type="Troubleshooting",
        title="Green Heel Tab Discoloring",
        content="Symptom: The signature green heel tab is fading or discoloring. Solution: This can happen with prolonged sun exposure or machine washing. Spot clean with a damp cloth only. If faded, a small amount of green leather dye can restore the color.",
    ),

    # ── nb-574 ────────────────────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-029",
        product_id="nb-574",
        document_type="Manual",
        title="New Balance 574 Suede and Mesh Care",
        content="The 574 combines suede overlays with a mesh base. Brush suede with a suede brush to restore nap. Spot clean mesh with mild detergent. Apply a suede protector spray before first wear. Do not machine wash — the ENCAP midsole can warp.",
    ),
    KnowledgeArticle(
        article_id="KA-030",
        product_id="nb-574",
        document_type="FAQ",
        title="574 Width Options",
        content="Q: Do the 574 come in wide sizes? A: Yes, the 574 is available in standard (D), wide (2E), and extra-wide (4E) for men, and narrow (2A), standard (B), and wide (D) for women. The suede/mesh upper stretches slightly with wear.",
    ),
    KnowledgeArticle(
        article_id="KA-031",
        product_id="nb-574",
        document_type="Troubleshooting",
        title="Suede Panels Staining from Rain",
        content="Symptom: Dark water marks on the suede panels after exposure to rain. This is the same water damage issue that affects the New Balance 990v6 pigskin suede — both shoes use untreated suede that stains permanently if not protected. Unlike synthetic mesh uppers (Nike Pegasus, ASICS Nimbus) that dry quickly without marks, suede requires preventive treatment. Solution: Let the shoes dry naturally at room temperature (never use heat, which shrinks and hardens suede). Once dry, brush with a suede brush in one direction to restore the nap. For stubborn stains, use a suede eraser. Prevent with a waterproof suede protector spray applied before first wear — this applies to any suede shoe.",
    ),
    KnowledgeArticle(
        article_id="KA-032",
        product_id="nb-574",
        document_type="Troubleshooting",
        title="Insole Sliding Out of Place",
        content="Symptom: The removable insole bunches up or slides forward while walking. Insole movement is a common issue across shoes with removable insoles — the ASICS Gel-Nimbus 26 OrthoLite insole and Brooks Ghost 16 insole both experience similar bunching and squeaking problems. Solution: Remove the insole and apply a thin line of double-sided tape or fabric glue along the heel area. Press the insole back in firmly. For squeaking (common when the insole rubs against the midsole), sprinkle baby powder or cornstarch on the midsole surface before replacing the insole. Replace worn insoles with New Balance supportive inserts or aftermarket insoles like Superfeet Green.",
    ),

    # ── nike-drifit-tee ──────────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-033",
        product_id="nike-drifit-tee",
        document_type="Manual",
        title="Nike Dri-FIT Shirt Washing Instructions",
        content="Machine wash cold with like colors. Do not use fabric softener — it coats the Dri-FIT fibers and reduces moisture-wicking performance. Tumble dry low or hang dry. Do not iron directly on the Dri-FIT logo or printed graphics.",
    ),
    KnowledgeArticle(
        article_id="KA-034",
        product_id="nike-drifit-tee",
        document_type="FAQ",
        title="Dri-FIT Shirt Odor Retention",
        content="Q: Why does my Dri-FIT shirt smell even after washing? A: Synthetic polyester fibers can trap bacteria that cause odor. Soak in a solution of white vinegar and cold water for 30 minutes before washing. Avoid fabric softener, which seals in odors.",
    ),
    KnowledgeArticle(
        article_id="KA-035",
        product_id="nike-drifit-tee",
        document_type="Troubleshooting",
        title="Dri-FIT No Longer Wicking Moisture",
        content="Symptom: The shirt absorbs sweat and clings instead of wicking it away. This wicking performance loss affects all synthetic moisture-management fabrics — Dri-FIT (Nike), AEROREADY (Adidas), and ColdGear (Under Armour) all use similar polyester-based fiber treatments that get coated and blocked by fabric softener or dryer sheets. Solution: Wash the garment in hot water with a cup of white vinegar (no detergent). Repeat if necessary. The wicking performance should restore after 1-2 vinegar washes. This same vinegar wash method works on any moisture-wicking apparel. Going forward, never use fabric softener or dryer sheets on any performance apparel.",
    ),
    KnowledgeArticle(
        article_id="KA-036",
        product_id="nike-drifit-tee",
        document_type="Troubleshooting",
        title="Shirt Pilling After Multiple Washes",
        content="Symptom: Small fabric balls (pills) forming on the surface. Solution: Turn the shirt inside out before washing. Use a gentle cycle and avoid washing with rough fabrics like denim or towels. Remove existing pills with a fabric shaver or sweater stone.",
    ),

    # ── adidas-running-shorts ────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-037",
        product_id="adidas-running-shorts",
        document_type="Manual",
        title="Adidas Running Shorts Care Guide",
        content="Wash cold with similar colors. The AEROREADY moisture-wicking fabric dries quickly — hang dry is recommended. Like Nike Dri-FIT and Under Armour ColdGear, the AEROREADY treatment is degraded by fabric softener and dryer sheets, which coat the synthetic fibers and block moisture transport. Never use fabric softener on any performance apparel. The built-in brief liner should be washed after every use to prevent bacterial buildup and odor retention — the same odor issue that affects Dri-FIT shirts. Do not use bleach.",
    ),
    KnowledgeArticle(
        article_id="KA-038",
        product_id="adidas-running-shorts",
        document_type="FAQ",
        title="Running Shorts Inseam Length",
        content="Q: What is the inseam length? A: The standard inseam is 5 inches. Adidas also offers a 3-inch split short and a 7-inch long option in the same AEROREADY fabric. Choose based on your comfort and range of motion preference.",
    ),
    KnowledgeArticle(
        article_id="KA-039",
        product_id="adidas-running-shorts",
        document_type="Troubleshooting",
        title="Inner Liner Chafing on Long Runs",
        content="Symptom: Chafing or irritation from the built-in brief liner during runs over 10 miles. Solution: Apply an anti-chafe balm (like Body Glide) to the inner thighs before running. If the liner seam is the issue, try wearing the shorts inside out or switch to a liner-less option.",
    ),
    KnowledgeArticle(
        article_id="KA-040",
        product_id="adidas-running-shorts",
        document_type="Troubleshooting",
        title="Drawstring Pulled Inside Waistband",
        content="Symptom: The drawstring has retracted into the waistband channel. Solution: Attach a safety pin to one end of the drawstring and thread it back through the channel. To prevent recurrence, tie a knot at each end of the drawstring that is wider than the channel opening.",
    ),

    # ── ua-coldgear ──────────────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-041",
        product_id="ua-coldgear",
        document_type="Manual",
        title="Under Armour ColdGear Layering Guide",
        content="The ColdGear base layer is designed as a first layer against the skin. Like Nike Dri-FIT and Adidas AEROREADY, the ColdGear fabric uses moisture-wicking synthetic fibers — but adds a dual-layer construction with a soft brushed interior that traps heat while the smooth exterior wicks moisture outward. For temperatures below 40°F, pair with a mid-layer fleece and a windproof outer shell. As with all moisture-wicking apparel, never use fabric softener or dryer sheets — they coat the fibers and destroy wicking performance. A white vinegar wash restores wicking if it has been compromised.",
    ),
    KnowledgeArticle(
        article_id="KA-042",
        product_id="ua-coldgear",
        document_type="FAQ",
        title="ColdGear Compression vs. Fitted",
        content="Q: What is the difference between ColdGear Compression and ColdGear Fitted? A: Compression fits skin-tight and provides muscle support for performance. Fitted sits close to the body without compression — it is more comfortable for casual cold-weather use. Both use the same dual-layer ColdGear fabric.",
    ),
    KnowledgeArticle(
        article_id="KA-043",
        product_id="ua-coldgear",
        document_type="Troubleshooting",
        title="Base Layer Shrinkage After Washing",
        content="Symptom: The ColdGear top feels tighter after washing. Solution: The polyester/elastane blend can shrink in hot water or a hot dryer. Always wash cold and tumble dry on low. If already shrunk, gently stretch the damp garment back to shape and lay flat to dry.",
    ),
    KnowledgeArticle(
        article_id="KA-044",
        product_id="ua-coldgear",
        document_type="Troubleshooting",
        title="Seam Splitting at Shoulder",
        content="Symptom: The seam is coming apart at the shoulder or armpit area. Solution: If this occurs within the warranty period, Under Armour will replace the item. For a temporary fix, use a needle and polyester thread to re-stitch the seam. Ensure you are wearing the correct size — a too-tight fit stresses seams.",
    ),

    # ── nike-running-socks ───────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-045",
        product_id="nike-running-socks",
        document_type="Manual",
        title="Nike Multiplier Running Socks Care",
        content="Machine wash warm with like colors. Tumble dry on medium heat — the Dri-FIT yarn maintains its wicking ability through many wash cycles. As with all Dri-FIT apparel (shirts, shorts) and other moisture-wicking fabrics like Adidas AEROREADY and Under Armour ColdGear, do not use fabric softener — it coats the synthetic fibers and stops moisture wicking. If wicking degrades, a white vinegar wash restores it. Turn inside out before washing to protect the cushioned sole.",
    ),
    KnowledgeArticle(
        article_id="KA-046",
        product_id="nike-running-socks",
        document_type="FAQ",
        title="Running Socks Sizing Guide",
        content="Q: How do I pick the right sock size? A: Nike running socks use shoe size ranges: S (3-5), M (6-8), L (8-12), XL (12-15). For between sizes, size up. The arch band should feel snug but not constricting. The socks are left/right specific — check the L/R markings.",
    ),
    KnowledgeArticle(
        article_id="KA-047",
        product_id="nike-running-socks",
        document_type="Troubleshooting",
        title="Socks Bunching Under Arch",
        content="Symptom: The sock fabric bunches or wrinkles under the arch during runs. Solution: This usually means the socks are too large. Try a smaller size. Ensure you are wearing the correct left/right sock — they are anatomically shaped. The arch band should sit snugly over the arch.",
    ),
    KnowledgeArticle(
        article_id="KA-048",
        product_id="nike-running-socks",
        document_type="Troubleshooting",
        title="Elastic Losing Stretch",
        content="Symptom: The arch band and cuff no longer grip the foot and ankle. Elastic and material degradation over time is a common issue across products that rely on stretch materials — latex resistance bands degrade from UV and heat exposure, EVA foam on the TriggerPoint foam roller cracks with heavy use and sunlight, and silicone gaskets on hydration flask caps lose their seal. Solution: Elastic degrades faster with hot water washing and high-heat drying. Replace running socks every 6-12 months depending on usage. Extend life by washing in cold water and air drying. Inspect elastic components regularly, just as you would inspect resistance bands for tears before each use.",
    ),

    # ── hydration-belt ───────────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-049",
        product_id="hydration-belt",
        document_type="Manual",
        title="Nathan Trail Mix Plus Assembly and Use",
        content="The belt comes with two 10oz flasks. Fill flasks with water or sports drink, insert into holsters, and adjust the elastic belt for a snug fit around the hips. The zippered pocket holds phones up to 6.7 inches. Rinse flasks after every use to prevent mildew.",
    ),
    KnowledgeArticle(
        article_id="KA-050",
        product_id="hydration-belt",
        document_type="FAQ",
        title="Compatible Flask Replacements",
        content="Q: Can I use third-party flasks? A: The Nathan Trail Mix Plus holsters are designed for Nathan 10oz flasks. Third-party flasks may not fit securely and could bounce out while running. Replacement Nathan flasks are available separately.",
    ),
    KnowledgeArticle(
        article_id="KA-051",
        product_id="hydration-belt",
        document_type="Troubleshooting",
        title="Flask Leaking from Cap",
        content="Symptom: Water leaks from the flask cap during running. Solution: Ensure the silicone bite valve is fully closed by pressing it flat. Check the cap gasket for cracks — a worn gasket will not seal properly. Replacement caps with gaskets are available from Nathan.",
    ),
    KnowledgeArticle(
        article_id="KA-052",
        product_id="hydration-belt",
        document_type="Troubleshooting",
        title="Mildew Smell in Flasks",
        content="Symptom: A musty or sour smell coming from the flasks. Odor retention in synthetic materials is a widespread issue — Dri-FIT polyester shirts trap bacteria that cause persistent odor, Adidas AEROREADY shorts liners develop bacterial buildup, and EVA foam rollers can off-gas chemical smells. With hydration flasks, the smell comes from mildew growth in trapped moisture. Solution: Fill each flask with a solution of 1 tablespoon baking soda per 10oz of warm water. Let soak overnight. Rinse thoroughly and air dry with caps off. This baking soda soak method also works for any odor-retaining sports equipment. For synthetic apparel odor, a white vinegar soak is more effective. Clean flasks after every use to prevent recurrence.",
    ),

    # ── foam-roller ──────────────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-053",
        product_id="foam-roller",
        document_type="Manual",
        title="TriggerPoint GRID Foam Roller Usage Guide",
        content="Place the foam roller on the ground and position the target muscle group on top. Use body weight to apply pressure. Roll slowly (1 inch per second) along the muscle belly. Spend 30-60 seconds on each area. The GRID pattern has three densities — use the flat zones for broad muscles and the finger-like nubs for deeper trigger points.",
    ),
    KnowledgeArticle(
        article_id="KA-054",
        product_id="foam-roller",
        document_type="FAQ",
        title="Foam Roller Firmness Selection",
        content="Q: Is the GRID too firm for beginners? A: The GRID has a medium-firm density suitable for most users. Beginners may feel discomfort on tight IT bands or calves — this is normal. Start with lighter pressure by supporting more weight with your arms. Progress to full body weight as tissues adapt.",
    ),
    KnowledgeArticle(
        article_id="KA-055",
        product_id="foam-roller",
        document_type="Troubleshooting",
        title="Foam Roller Surface Cracking",
        content="Symptom: The EVA foam surface is developing cracks or dents. Material degradation from UV exposure and heat affects many sports products — latex resistance bands become brittle and can snap, elastic in running socks loses stretch, and silicone gaskets on hydration flask caps crack and leak. With the GRID foam roller, EVA foam is particularly susceptible to UV damage. Solution: This occurs with heavy use or if the roller is stored in direct sunlight or extreme heat. The GRID's ABS plastic core should remain intact even if the outer EVA foam degrades. If the foam is severely cracked, it is time for a replacement. Store all sports equipment in a cool, dry place away from direct sunlight — this extends the life of foam, latex, elastic, and silicone components alike.",
    ),
    KnowledgeArticle(
        article_id="KA-056",
        product_id="foam-roller",
        document_type="Troubleshooting",
        title="Foam Roller Not Relieving Tightness",
        content="Symptom: Rolling does not seem to release muscle tension. Solution: Ensure you are rolling slowly and pausing on trigger points for 20-30 seconds rather than quickly rolling back and forth. Apply more pressure by stacking limbs (e.g., cross one leg over the other for calves). Consider a firmer roller or a lacrosse ball for deep tissue work.",
    ),

    # ── resistance-bands ─────────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-057",
        product_id="resistance-bands",
        document_type="Manual",
        title="Theraband Resistance Bands Exercise Guide",
        content="The set includes 5 bands with progressive resistance: Yellow (extra light), Red (light), Green (medium), Blue (heavy), and Black (extra heavy). Begin with the lighter bands and progress as strength increases. Inspect bands before each use for tears or nicks. Anchor bands securely and maintain controlled movements.",
    ),
    KnowledgeArticle(
        article_id="KA-058",
        product_id="resistance-bands",
        document_type="FAQ",
        title="Resistance Band Selection for Rehab",
        content="Q: Which band should I use for physical therapy exercises? A: Start with the Yellow (extra light) or Red (light) band. Physical therapy exercises require controlled, low-resistance movements. Your physical therapist can recommend the appropriate color based on your recovery stage.",
    ),
    KnowledgeArticle(
        article_id="KA-059",
        product_id="resistance-bands",
        document_type="Troubleshooting",
        title="Resistance Band Snapped During Use",
        content="Symptom: A band broke mid-exercise. Latex and rubber material degradation from UV, heat, and age is a safety concern across many products — EVA foam on the TriggerPoint foam roller cracks under the same conditions, elastic in Nike running socks loses stretch, and silicone gaskets on hydration flask caps fail. With resistance bands, the consequence of degradation is more immediate and dangerous. Solution: Always inspect bands for small tears, discoloration, or thin spots before each use. Replace bands that show any signs of wear. Store in a cool, dry place away from direct sunlight — the same storage advice applies to foam rollers, latex products, and any equipment with elastic or rubber components.",
    ),
    KnowledgeArticle(
        article_id="KA-060",
        product_id="resistance-bands",
        document_type="Troubleshooting",
        title="Bands Rolling Up During Exercises",
        content="Symptom: The flat band rolls into a tube shape during leg exercises. Solution: Use a wider grip or stance to keep the band flat under tension. For lower-body exercises, consider fabric loop bands which are less prone to rolling. Ensure the band is evenly distributed and not twisted before starting the exercise.",
    ),

    # ── garmin-forerunner-265 ────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-061",
        product_id="garmin-forerunner-265",
        document_type="Manual",
        title="Garmin Forerunner 265 Initial Setup",
        content="Charge the watch fully before first use via the included USB-C cable. Download the Garmin Connect app on your phone and pair via Bluetooth. Enable multi-band GPS in Settings > Activities for the most accurate pace and distance. Set up heart rate zones based on your lactate threshold or max heart rate.",
    ),
    KnowledgeArticle(
        article_id="KA-062",
        product_id="garmin-forerunner-265",
        document_type="FAQ",
        title="Forerunner 265 Battery Life Tips",
        content="Q: How do I maximize battery life? A: The AMOLED display is the biggest battery drain. Enable Always-On Display only during activities. Use standard GPS instead of multi-band for training runs. Reduce screen brightness and notification frequency. In GPS mode, expect 20 hours; in smartwatch mode, up to 13 days.",
    ),
    KnowledgeArticle(
        article_id="KA-063",
        product_id="garmin-forerunner-265",
        document_type="Troubleshooting",
        title="GPS Takes Too Long to Lock",
        content="Symptom: GPS satellite acquisition takes more than 60 seconds. Solution: Ensure the watch firmware is up to date — Garmin pushes satellite almanac data via updates. Stand in an open area away from tall buildings. If the issue persists, perform a hard reset by holding the LIGHT button for 15 seconds. Re-sync with Garmin Connect.",
    ),
    KnowledgeArticle(
        article_id="KA-064",
        product_id="garmin-forerunner-265",
        document_type="Troubleshooting",
        title="Optical Heart Rate Reads Inaccurately",
        content="Symptom: Heart rate spikes to unrealistic values or drops to zero during runs. Solution: Wear the watch snugly on your wrist, about one finger-width above the wrist bone. The optical sensor struggles with dark tattoos — consider a chest strap (e.g., Garmin HRM-Pro Plus) for better accuracy. Clean the sensor with rubbing alcohol if dirty.",
    ),

    # ── rei-half-dome-tent ───────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-065",
        product_id="rei-half-dome-tent",
        document_type="Manual",
        title="REI Half Dome SL 2+ Pitching Instructions",
        content="Layout the footprint (sold separately) first, then the tent body. Insert the color-coded aluminum poles into the corresponding grommets — green to green, gray to gray. Clip the tent body to the poles. Drape the rainfly over the top and secure with Velcro tabs. Stake out all guylines for wind resistance.",
    ),
    KnowledgeArticle(
        article_id="KA-066",
        product_id="rei-half-dome-tent",
        document_type="FAQ",
        title="Half Dome SL 2+ in Heavy Rain",
        content="Q: How waterproof is the Half Dome? A: The rainfly uses a 1500mm polyurethane coating and factory-taped seams. The tub floor has a 3000mm rating. It handles heavy rain well for a 3-season tent. Water resistance varies widely across outdoor and athletic products — the Kelty Cosmic sleeping bag uses a DriDown hydrophobic treatment that repels moisture but is not waterproof, while suede shoes like the New Balance 990v6 and 574 have no water resistance at all and stain permanently when wet. In prolonged downpours, avoid touching the inner tent body against the rainfly to prevent water transfer, and keep your sleeping bag in a dry bag inside the tent.",
    ),
    KnowledgeArticle(
        article_id="KA-067",
        product_id="rei-half-dome-tent",
        document_type="Troubleshooting",
        title="Condensation on Inner Tent Walls",
        content="Symptom: Water droplets on the inside of the tent walls in the morning. Solution: This is condensation from breathing, not a leak. Open both vestibule doors partially and the ceiling vent to improve airflow. Camp away from water sources. In humid conditions, some condensation is unavoidable.",
    ),
    KnowledgeArticle(
        article_id="KA-068",
        product_id="rei-half-dome-tent",
        document_type="Troubleshooting",
        title="Pole Sleeve Torn at Corner",
        content="Symptom: The fabric sleeve where the pole inserts has ripped. Solution: This is often caused by forcing a bent pole into the grommet. Apply Tenacious Tape over the tear as a field repair. For permanent repair, REI offers a lifetime warranty — bring the tent to any REI store for assessment.",
    ),

    # ── nemo-disco-sleeping-bag ──────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-069",
        product_id="nemo-disco-sleeping-bag",
        document_type="Manual",
        title="NEMO Disco 30 Sleeping Bag Care",
        content="Store the Disco 30 uncompressed in the included cotton storage sack — never in the stuff sack for long periods. Wash in a front-loading machine with a technical fabric cleaner on a gentle cycle. Tumble dry low with clean tennis balls to restore loft. The spoon shape provides extra room at knees and elbows for side sleepers.",
    ),
    KnowledgeArticle(
        article_id="KA-070",
        product_id="nemo-disco-sleeping-bag",
        document_type="FAQ",
        title="Disco 30 Temperature Rating",
        content="Q: Will the Disco 30 keep me warm at 30°F? A: The 30°F rating is the lower limit — you will survive but may not be comfortable. For comfortable sleep, use the Disco 30 in temperatures above 40°F. Pair with a sleeping pad with an R-value of 3 or higher for insulation from the ground.",
    ),
    KnowledgeArticle(
        article_id="KA-071",
        product_id="nemo-disco-sleeping-bag",
        document_type="Troubleshooting",
        title="Synthetic Fill Losing Loft",
        content="Symptom: The sleeping bag feels thinner and less warm than when new. Insulation loft loss is common across sleeping bags — the Kelty Cosmic 20 down fill clumps when wet, and synthetic fill in the Disco 30 compresses permanently when stored in a stuff sack. This is similar to how foam midsoles in running shoes (React, Boost, DNA Loft, FF Blast Plus) lose their responsiveness and cushion over time from repeated compression. Solution: Wash with technical fabric cleaner and tumble dry on low with 2-3 clean tennis balls to restore some loft (the tennis ball method works for both synthetic and down bags). If the bag has been stored compressed in a stuff sack for months, the synthetic fill may not fully recover. Always store sleeping bags uncompressed in an oversized cotton storage sack.",
    ),
    KnowledgeArticle(
        article_id="KA-072",
        product_id="nemo-disco-sleeping-bag",
        document_type="Troubleshooting",
        title="Zipper Snagging on Draft Tube",
        content="Symptom: The main zipper catches on the internal draft tube fabric. Solution: Hold the draft tube fabric flat with one hand while operating the zipper with the other. If the zipper slider is bent, gently squeeze it with pliers to restore its shape. Apply a zipper lubricant wax for smoother operation.",
    ),

    # ── msr-hubba-hubba-tent ─────────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-073",
        product_id="msr-hubba-hubba-tent",
        document_type="Manual",
        title="MSR Hubba Hubba NX 2 Setup Guide",
        content="Unfold the tent body and stake out the four corners. Assemble the two hubbed pole sets and insert into the corner grommets. The tent body clips to the poles — no sleeves needed. Attach the rainfly with the buckles at each corner. Both vestibule doors open from either side for easy access.",
    ),
    KnowledgeArticle(
        article_id="KA-074",
        product_id="msr-hubba-hubba-tent",
        document_type="FAQ",
        title="Hubba Hubba Footprint Necessity",
        content="Q: Do I need the MSR footprint? A: A footprint extends the life of the tent floor and adds waterproofing, but adds weight (5oz). On rocky or abrasive ground, it is highly recommended. On soft grass or established tent pads, you can skip it to save weight.",
    ),
    KnowledgeArticle(
        article_id="KA-075",
        product_id="msr-hubba-hubba-tent",
        document_type="Troubleshooting",
        title="Rainfly Pooling Water on Top",
        content="Symptom: Water collects in a pool on the rainfly during rain. Solution: Ensure the rainfly is taut by tightening the corner buckles and staking out the guylines. The symmetrical design requires even tension on all sides. If the poles are bent or damaged, the fly will sag — inspect and replace damaged pole sections.",
    ),
    KnowledgeArticle(
        article_id="KA-076",
        product_id="msr-hubba-hubba-tent",
        document_type="Troubleshooting",
        title="Pole Hub Cracked",
        content="Symptom: The central hub connector where the pole sections meet has cracked or split. Solution: MSR offers replacement hub connectors as spare parts. In the field, splint the hub with a pole repair sleeve and duct tape. Contact MSR for a warranty replacement — the hubs are covered against manufacturing defects.",
    ),

    # ── kelty-cosmic-sleeping-bag ────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-077",
        product_id="kelty-cosmic-sleeping-bag",
        document_type="Manual",
        title="Kelty Cosmic 20 Down Sleeping Bag Storage",
        content="Never store the Cosmic 20 in its stuff sack for extended periods — this compresses the 550-fill DriDown and destroys loft. Use the included oversized cotton storage bag. Hang in a dry closet if possible. The DriDown treatment repels moisture but the bag should still be kept dry.",
    ),
    KnowledgeArticle(
        article_id="KA-078",
        product_id="kelty-cosmic-sleeping-bag",
        document_type="FAQ",
        title="Cosmic 20 DriDown Explained",
        content="Q: What is DriDown? A: DriDown is a hydrophobic treatment applied to each individual down cluster. It repels moisture and dries 33% faster than untreated down. This means the bag retains more warmth if exposed to humidity, but it is not waterproof — keep the bag in a dry bag inside your tent. Water resistance varies across product types: tent rainflies use polyurethane coatings (the REI Half Dome has a 1500mm rating), synthetic sleeping bags like the NEMO Disco handle moisture better than down, and suede shoes (New Balance 990v6, 574) have no water resistance at all. Always match your gear's water resistance level to the conditions.",
    ),
    KnowledgeArticle(
        article_id="KA-079",
        product_id="kelty-cosmic-sleeping-bag",
        document_type="Troubleshooting",
        title="Down Clumping After Getting Wet",
        content="Symptom: The down fill has clumped into balls and the bag has cold spots. Solution: Tumble dry on low heat with 2-3 clean tennis balls for 60-90 minutes. The tennis balls break apart the clumps. Do not air dry a down bag — it takes too long and risks mildew. Repeat the dryer cycle if clumps remain.",
    ),
    KnowledgeArticle(
        article_id="KA-080",
        product_id="kelty-cosmic-sleeping-bag",
        document_type="Troubleshooting",
        title="Feathers Poking Through Shell Fabric",
        content="Symptom: Small feathers are poking through the nylon shell. Solution: This is normal for down sleeping bags. Do not pull the feather out — push it back in from the outside and massage the fabric closed. Pulling feathers enlarges the hole and allows more to escape. A small amount of feather migration does not affect warmth.",
    ),

    # ── therm-a-rest-sleeping-pad ────────────────────────────────────────
    KnowledgeArticle(
        article_id="KA-081",
        product_id="therm-a-rest-sleeping-pad",
        document_type="Manual",
        title="Therm-a-Rest NeoAir XTherm Inflation and Deflation",
        content="Inflate using the included pump sack — avoid blowing into the valve with your mouth, as moisture from breath can degrade the internal reflective layers over time. Open the flat valve and attach the pump sack. Squeeze air in 5-8 pump cycles. Fine-tune firmness by opening the valve briefly. To deflate, open the valve wide and roll from the opposite end.",
    ),
    KnowledgeArticle(
        article_id="KA-082",
        product_id="therm-a-rest-sleeping-pad",
        document_type="FAQ",
        title="NeoAir XTherm R-Value Explained",
        content="Q: What does an R-value of 6.9 mean? A: R-value measures thermal resistance — how well the pad insulates you from the cold ground. The XTherm's 6.9 rating makes it suitable for 4-season use, including winter camping on snow. For comparison, a summer pad typically has an R-value of 1-2.",
    ),
    KnowledgeArticle(
        article_id="KA-083",
        product_id="therm-a-rest-sleeping-pad",
        document_type="Troubleshooting",
        title="Pad Deflates Overnight",
        content="Symptom: The pad is mostly flat by morning even after full inflation. Solution: Temperature drops cause air to contract, which is normal and minor. If significantly deflated, there is a leak. Inflate the pad, submerge sections in water, and look for bubbles. Mark the hole and apply the included repair patch. Therm-a-Rest also offers a professional repair service.",
    ),
    KnowledgeArticle(
        article_id="KA-084",
        product_id="therm-a-rest-sleeping-pad",
        document_type="Troubleshooting",
        title="Valve Not Sealing Properly",
        content="Symptom: Air hisses from the valve even when closed. Solution: Check for debris (sand, dirt) in the valve mechanism. Rinse the valve under clean water while opening and closing it several times. Ensure the valve flap is fully pressed down and rotated to the locked position. If the valve is physically damaged, contact Therm-a-Rest for warranty replacement.",
    ),
]


# ---------------------------------------------------------------------------
# Support Tickets  (84 total — 4 per product)
# ---------------------------------------------------------------------------

SUPPORT_TICKETS: list[SupportTicket] = [
    # ── nike-pegasus-40 ───────────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-001",
        product_id="nike-pegasus-40",
        status="Closed",
        issue_description="The cushion on my Pegasus 40 feels completely dead after 4 months of running. The React foam has no bounce left.",
        resolution_text="Customer had logged approximately 400 miles. Explained that cushion responsiveness loss is expected across all foam midsole technologies (React, Boost, FF Blast Plus, DNA Loft) after 300-500 miles. Running shoes should be replaced at that interval. Rotating between two pairs extends midsole life. Offered 15% discount on next purchase.",
    ),
    SupportTicket(
        ticket_id="T-002",
        product_id="nike-pegasus-40",
        status="Closed",
        issue_description="Getting blisters on both heels after every run.",
        resolution_text="Advised customer to use heel-lock lacing technique. Also recommended thicker cushioned socks. Customer reported improvement after one week.",
    ),
    SupportTicket(
        ticket_id="T-003",
        product_id="nike-pegasus-40",
        status="Closed",
        issue_description="Ordered size 10 but they feel too narrow in the midfoot.",
        resolution_text="Exchanged for size 10 Wide (2E). Customer confirmed improved fit.",
    ),
    SupportTicket(
        ticket_id="T-004",
        product_id="nike-pegasus-40",
        status="Open",
        issue_description="The outsole is separating from the midsole on the left shoe after only 6 weeks of use. Looks like the glue is failing at the toe area.",
        resolution_text="",
    ),

    # ── adidas-ultraboost-24 ──────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-005",
        product_id="adidas-ultraboost-24",
        status="Closed",
        issue_description="The Boost midsole has turned yellow and looks terrible. I keep them indoors so I do not understand why this is happening.",
        resolution_text="Explained that yellowing from oxidation is cosmetic and does not affect performance. This same yellowing issue affects any white foam or rubber midsole — Nike Air Max 90, Adidas Stan Smith, and New Balance 574 owners report it too. Provided the baking soda and hydrogen peroxide paste cleaning method, which works across all yellowed midsoles. Recommended storing shoes away from sunlight to slow oxidation.",
    ),
    SupportTicket(
        ticket_id="T-006",
        product_id="adidas-ultraboost-24",
        status="Closed",
        issue_description="The Continental rubber outsole is peeling off at the toe area. The outsole is separating from the Boost midsole.",
        resolution_text="Outsole separation is a known issue on the Ultraboost, particularly at the toe where flex stress is highest. This outsole delamination issue has also been reported on the Nike Pegasus and Brooks Ghost, though less frequently. Confirmed shoe was within 6-month warranty. Processed replacement pair. For future reference, Shoe Goo adhesive can provide a temporary fix for minor separation. Advised against leaving shoes in hot environments (car trunk, direct sunlight) as heat weakens the adhesive bond.",
    ),
    SupportTicket(
        ticket_id="T-007",
        product_id="adidas-ultraboost-24",
        status="Closed",
        issue_description="The Primeknit upper feels really tight across the top of my foot.",
        resolution_text="Advised customer that Primeknit stretches with wear. Suggested loosening laces and removing insole temporarily. If still tight after 2 weeks, exchange for half size up.",
    ),
    SupportTicket(
        ticket_id="T-008",
        product_id="adidas-ultraboost-24",
        status="Open",
        issue_description="Primeknit upper developed a hole near the pinky toe after 3 months of daily wear.",
        resolution_text="",
    ),

    # ── nb-990v6 ──────────────────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-009",
        product_id="nb-990v6",
        status="Closed",
        issue_description="Water stains on the suede panels after wearing in light rain. Dark blotchy marks on the pigskin suede that won't come out.",
        resolution_text="Water damage to suede is one of the most common complaints across suede shoes — the New Balance 574 has the same issue with its suede panels. Unlike synthetic mesh uppers that dry without marks, untreated suede stains permanently. Provided suede cleaning instructions: let dry naturally at room temperature, brush with suede brush in one direction, use suede eraser for stubborn stains. Recommended suede protector spray for future prevention — this applies to any suede shoe. Sent complimentary suede care kit.",
    ),
    SupportTicket(
        ticket_id="T-010",
        product_id="nb-990v6",
        status="Closed",
        issue_description="The shoes feel very stiff and uncomfortable compared to my old 990v5. The ENCAP midsole has no give at all.",
        resolution_text="Break-in stiffness is common across products with firm materials — the Adidas Stan Smith leather upper requires about a week of short-wear break-in, and the Under Armour ColdGear compression fit feels too tight initially. The 990v6 ENCAP midsole uses a firmer compound than the v5 for improved durability. Allow 20-30 miles of break-in. Customer reported improved comfort after 2 weeks.",
    ),
    SupportTicket(
        ticket_id="T-011",
        product_id="nb-990v6",
        status="Closed",
        issue_description="The lace eyelet on the left shoe tore out of the upper.",
        resolution_text="Manufacturing defect confirmed. Processed warranty replacement.",
    ),
    SupportTicket(
        ticket_id="T-012",
        product_id="nb-990v6",
        status="Open",
        issue_description="At $200 these are the most expensive shoes I have ever bought and the suede is already peeling after 2 months.",
        resolution_text="",
    ),

    # ── asics-gel-nimbus-26 ───────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-013",
        product_id="asics-gel-nimbus-26",
        status="Closed",
        issue_description="There is a hard lump under my left heel that is painful to run on.",
        resolution_text="Identified as a PureGEL manufacturing defect. Issued full replacement pair.",
    ),
    SupportTicket(
        ticket_id="T-014",
        product_id="asics-gel-nimbus-26",
        status="Closed",
        issue_description="The mesh on the toe box is tearing. I have only worn them for 2 months.",
        resolution_text="Customer was wearing a half size too small. Exchanged for correct size and provided fit guide.",
    ),
    SupportTicket(
        ticket_id="T-015",
        product_id="asics-gel-nimbus-26",
        status="Closed",
        issue_description="I overpronate and the shoe does not provide enough support.",
        resolution_text="Explained the Nimbus is a neutral shoe. Recommended the ASICS Kayano 30 with 4D Guidance System for pronation support. Processed exchange.",
    ),
    SupportTicket(
        ticket_id="T-016",
        product_id="asics-gel-nimbus-26",
        status="Open",
        issue_description="The OrthoLite X-55 insole keeps sliding out of position during runs, bunching up under the arch. Same issue I had with my New Balance 574.",
        resolution_text="",
    ),

    # ── brooks-ghost-16 ──────────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-017",
        product_id="brooks-ghost-16",
        status="Closed",
        issue_description="My Ghost 16s make a loud squeaking noise with every step.",
        resolution_text="Advised customer to remove insole and apply baby powder on the midsole surface. Squeak stopped immediately.",
    ),
    SupportTicket(
        ticket_id="T-018",
        product_id="brooks-ghost-16",
        status="Closed",
        issue_description="The outer edge of the sole is worn down way more than the rest after just 200 miles. The outsole is also starting to separate from the DNA Loft v2 midsole at the heel.",
        resolution_text="Explained this is a supination (underpronation) wear pattern. Outsole separation at the heel is related to the uneven compression from supination — a similar outsole delamination issue is commonly reported on the Adidas Ultraboost Continental outsole and Nike Pegasus. For the Ghost 16, the DNA Loft v2 midsole will compress unevenly over time. Shoe Goo adhesive can temporarily fix minor outsole separation. Recommended replacement every 300-400 miles.",
    ),
    SupportTicket(
        ticket_id="T-019",
        product_id="brooks-ghost-16",
        status="Closed",
        issue_description="I need more arch support than the Ghost provides. My feet ache after long runs.",
        resolution_text="Recommended the Brooks Adrenaline GTS for built-in arch support. Also suggested trying aftermarket insoles (e.g., Superfeet Green) in the Ghost 16.",
    ),
    SupportTicket(
        ticket_id="T-020",
        product_id="brooks-ghost-16",
        status="Open",
        issue_description="The tongue keeps sliding to the side during runs. Very annoying.",
        resolution_text="",
    ),

    # ── nike-air-max-90 ──────────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-021",
        product_id="nike-air-max-90",
        status="Closed",
        issue_description="The visible Air bubble in the heel has completely deflated on one shoe.",
        resolution_text="Confirmed shoe was within 2-year warranty period. Processed full replacement.",
    ),
    SupportTicket(
        ticket_id="T-022",
        product_id="nike-air-max-90",
        status="Closed",
        issue_description="The white midsole has turned yellow. I have only owned them for 6 months. The Air unit also looks discolored.",
        resolution_text="Yellowing from UV exposure and oxidation is the most common cosmetic complaint across shoes with white midsoles — Adidas Ultraboost Boost foam, Adidas Stan Smith rubber midsole, and New Balance 574 ENCAP midsole all experience the same issue. Provided the baking soda and hydrogen peroxide paste cleaning method, which works across all yellowed midsoles. For the Air Max 90 specifically, the salon-grade hydrogen peroxide cream with plastic wrap in sunlight for 3-4 hours gives the best results. Advised storing shoes away from direct sunlight to prevent recurrence.",
    ),
    SupportTicket(
        ticket_id="T-023",
        product_id="nike-air-max-90",
        status="Closed",
        issue_description="I wore these for a 5K run and my knees hurt afterwards.",
        resolution_text="Explained the Air Max 90 is a lifestyle sneaker, not a performance running shoe. Recommended dedicated running shoes for exercise.",
    ),
    SupportTicket(
        ticket_id="T-024",
        product_id="nike-air-max-90",
        status="Open",
        issue_description="Paint is chipping off the leather panels after only 3 months of normal wear.",
        resolution_text="",
    ),

    # ── adidas-stan-smith ────────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-025",
        product_id="adidas-stan-smith",
        status="Closed",
        issue_description="Deep cracks forming on the leather across the toe box area.",
        resolution_text="Advised customer to apply leather conditioner immediately. Explained that regular conditioning prevents cracking. Sent care guide and recommended cedar shoe trees.",
    ),
    SupportTicket(
        ticket_id="T-026",
        product_id="adidas-stan-smith",
        status="Closed",
        issue_description="The shoes are extremely stiff and painful to wear. The leather has no flex at all.",
        resolution_text="Break-in discomfort is common across products with rigid materials. The Stan Smith full-grain leather takes about a week of short-period wear. By comparison, the New Balance 990v6 ENCAP midsole needs 20-30 miles of break-in, and the Under Armour ColdGear compression fit feels too tight initially. Suggested wearing thick socks for short periods (1-2 hours) to accelerate the leather softening process. The leather will conform to the foot shape within a week.",
    ),
    SupportTicket(
        ticket_id="T-027",
        product_id="adidas-stan-smith",
        status="Closed",
        issue_description="The green heel tab color has completely faded.",
        resolution_text="Customer admitted to machine washing the shoes regularly. Advised spot cleaning only. Suggested green leather dye to restore the heel tab color.",
    ),
    SupportTicket(
        ticket_id="T-028",
        product_id="adidas-stan-smith",
        status="Open",
        issue_description="The leather is peeling off in large flakes on both shoes after 4 months.",
        resolution_text="",
    ),

    # ── nb-574 ────────────────────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-029",
        product_id="nb-574",
        status="Closed",
        issue_description="Got caught in the rain and now there are dark water marks all over the suede panels. Same thing happened to my 990v6 last year.",
        resolution_text="Water damage to suede is the most common complaint across the New Balance suede lineup — both the 574 and the 990v6 pigskin suede are affected. Unlike weather-treated products like the Kelty Cosmic DriDown sleeping bag or tent rainfly coatings, suede has no inherent water resistance. Advised letting shoes dry naturally at room temperature (never use heat), then brushing with suede brush in one direction. Sent a suede protector spray — this should be applied before first wear on any suede shoe to prevent staining.",
    ),
    SupportTicket(
        ticket_id="T-030",
        product_id="nb-574",
        status="Closed",
        issue_description="The insole keeps bunching up under my foot while walking. It slides forward and bunches under the arch.",
        resolution_text="Insole slippage is a common issue across shoes with removable insoles — the ASICS Gel-Nimbus 26 OrthoLite insole has the same bunching problem, and the Brooks Ghost 16 insole creates friction squeaking against the midsole. Suggested applying double-sided tape or fabric glue to the heel area of the insole. For squeaking, baby powder or cornstarch between the insole and midsole eliminates friction. Also recommended upgrading to aftermarket insoles like Superfeet Green or New Balance supportive inserts for better fit and arch support.",
    ),
    SupportTicket(
        ticket_id="T-031",
        product_id="nb-574",
        status="Closed",
        issue_description="Ordered standard width but they are very narrow on my feet.",
        resolution_text="Exchanged for wide (2E) width. Customer confirmed much better fit.",
    ),
    SupportTicket(
        ticket_id="T-032",
        product_id="nb-574",
        status="Open",
        issue_description="The ENCAP midsole is crumbling and leaving bits of foam on the ground.",
        resolution_text="",
    ),

    # ── nike-drifit-tee ──────────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-033",
        product_id="nike-drifit-tee",
        status="Closed",
        issue_description="The shirt stinks even right after washing. The odor is embedded in the fabric.",
        resolution_text="Advised soaking in white vinegar and cold water for 30 minutes before washing. Reminded customer not to use fabric softener, which traps odor in synthetic fibers.",
    ),
    SupportTicket(
        ticket_id="T-034",
        product_id="nike-drifit-tee",
        status="Closed",
        issue_description="The Dri-FIT is not wicking moisture anymore. My shirt gets soaked during runs instead of staying dry.",
        resolution_text="Customer had been using fabric softener, which coats synthetic fibers and blocks moisture transport. This wicking performance loss affects all moisture-wicking fabrics — Dri-FIT (Nike), AEROREADY (Adidas), and ColdGear (Under Armour) are all degraded by fabric softener and dryer sheets. Advised washing in hot water with a cup of white vinegar (no detergent) to strip the coating. This vinegar wash method works on any moisture-wicking apparel. Wicking restored after two washes. Advised never using fabric softener on any performance apparel going forward.",
    ),
    SupportTicket(
        ticket_id="T-035",
        product_id="nike-drifit-tee",
        status="Closed",
        issue_description="The shirt is covered in little fabric balls after 5 washes.",
        resolution_text="Advised turning shirt inside out before washing, using gentle cycle, and avoiding washing with rough fabrics. Suggested a fabric shaver to remove existing pills.",
    ),
    SupportTicket(
        ticket_id="T-036",
        product_id="nike-drifit-tee",
        status="Open",
        issue_description="The Dri-FIT logo is peeling off after just a few washes. I followed the care instructions.",
        resolution_text="",
    ),

    # ── adidas-running-shorts ────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-037",
        product_id="adidas-running-shorts",
        status="Closed",
        issue_description="The inner liner is causing terrible chafing on runs over 8 miles.",
        resolution_text="Recommended applying anti-chafe balm (Body Glide) to inner thighs before running. Also suggested trying the liner-less version of the shorts.",
    ),
    SupportTicket(
        ticket_id="T-038",
        product_id="adidas-running-shorts",
        status="Closed",
        issue_description="The drawstring got pulled completely inside the waistband during washing.",
        resolution_text="Walked customer through threading the drawstring back using a safety pin. Advised tying knots at each end to prevent recurrence.",
    ),
    SupportTicket(
        ticket_id="T-039",
        product_id="adidas-running-shorts",
        status="Closed",
        issue_description="The AEROREADY fabric is not drying quickly like it used to. The shorts stay damp and heavy during runs.",
        resolution_text="Customer was using fabric softener, which coats and blocks moisture-wicking synthetic fibers. This is the exact same issue that affects Nike Dri-FIT shirts and Under Armour ColdGear base layers — all moisture-wicking fabrics are degraded by fabric softener and dryer sheets. Advised washing in hot water with white vinegar (no detergent) to strip the coating. This vinegar wash restores wicking on any moisture-management apparel. Wicking performance returned after two washes.",
    ),
    SupportTicket(
        ticket_id="T-040",
        product_id="adidas-running-shorts",
        status="Open",
        issue_description="The side seam split open during a race at mile 8. Very embarrassing.",
        resolution_text="",
    ),

    # ── ua-coldgear ──────────────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-041",
        product_id="ua-coldgear",
        status="Closed",
        issue_description="My ColdGear base layer shrunk significantly after the first wash.",
        resolution_text="Customer washed in hot water and used a hot dryer. Advised always washing cold and tumble drying low. Processed exchange for a new base layer in correct size.",
    ),
    SupportTicket(
        ticket_id="T-042",
        product_id="ua-coldgear",
        status="Closed",
        issue_description="The seam at the left shoulder is coming apart after 3 months.",
        resolution_text="Confirmed manufacturing defect. Processed warranty replacement. Verified customer was wearing correct size.",
    ),
    SupportTicket(
        ticket_id="T-043",
        product_id="ua-coldgear",
        status="Closed",
        issue_description="I bought the compression fit thinking it was like a regular base layer. It is way too tight and uncomfortable. Similar to how stiff my Stan Smiths felt out of the box.",
        resolution_text="Break-in and fit adjustment is common across athletic products — the Adidas Stan Smith leather needs about a week to soften, the New Balance 990v6 ENCAP midsole requires 20-30 miles, and ColdGear Compression is intentionally skin-tight for muscle support. Explained the difference between ColdGear Compression (skin-tight, performance) and ColdGear Fitted (close but comfortable). Exchanged for Fitted version, which provides the same dual-layer moisture-wicking fabric without the compression.",
    ),
    SupportTicket(
        ticket_id="T-044",
        product_id="ua-coldgear",
        status="Open",
        issue_description="The brushed interior is pilling badly after only a few wears. Feels rough against my skin now. My Nike Dri-FIT shirts have the same pilling problem.",
        resolution_text="",
    ),

    # ── nike-running-socks ───────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-045",
        product_id="nike-running-socks",
        status="Closed",
        issue_description="The socks keep bunching up under my arches during long runs.",
        resolution_text="Customer was wearing size L (8-12) with size 8 shoes. Recommended downsizing to M (6-8) for a snugger fit. Also reminded about L/R specific socks.",
    ),
    SupportTicket(
        ticket_id="T-046",
        product_id="nike-running-socks",
        status="Closed",
        issue_description="The elastic in the arch band is completely gone after 4 months. The Dri-FIT wicking still works but the socks won't stay up.",
        resolution_text="Elastic and stretch material degradation from heat is a common issue across products — latex resistance bands become brittle from UV and heat, EVA foam on foam rollers cracks, and silicone gaskets on hydration flask caps lose their seal. With socks, hot water washing and high-heat drying accelerate elastic breakdown. Advised cold washing and low-heat or air drying to extend elastic life. Running socks should be replaced every 6-12 months. Provided a replacement pack as a courtesy.",
    ),
    SupportTicket(
        ticket_id="T-047",
        product_id="nike-running-socks",
        status="Closed",
        issue_description="I only received one pair but the listing says 2-Pack.",
        resolution_text="Shipping error confirmed. Sent the missing pair immediately via expedited shipping.",
    ),
    SupportTicket(
        ticket_id="T-048",
        product_id="nike-running-socks",
        status="Open",
        issue_description="Developed a blister on my right foot from the toe seam. The seam is raised and rough on the inside.",
        resolution_text="",
    ),

    # ── hydration-belt ───────────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-049",
        product_id="hydration-belt",
        status="Closed",
        issue_description="One of the flasks leaks from the cap every time I run.",
        resolution_text="Identified a cracked cap gasket. Shipped a replacement cap with new gasket free of charge.",
    ),
    SupportTicket(
        ticket_id="T-050",
        product_id="hydration-belt",
        status="Closed",
        issue_description="The flasks have a horrible mildew smell that I cannot get rid of. I have tried rinsing with hot water but the odor comes back.",
        resolution_text="Odor retention in synthetic materials is a widespread issue — Dri-FIT polyester shirts trap bacteria that cause persistent odor, AEROREADY shorts liners develop bacterial buildup, and EVA foam rollers can off-gas chemical smells. With hydration flasks, the mildew smell comes from trapped moisture. Advised soaking in baking soda solution (1 tbsp per 10oz warm water) overnight — this baking soda method works for any odor-retaining sports equipment. For synthetic apparel odor, white vinegar soaking is more effective. Reminded customer to rinse and air-dry flasks with caps off after every single use to prevent mildew recurrence.",
    ),
    SupportTicket(
        ticket_id="T-051",
        product_id="hydration-belt",
        status="Closed",
        issue_description="The belt bounces too much when I run. It will not stay in place.",
        resolution_text="Advised customer to tighten the belt so it sits snugly on the hips, not the waist. The belt should ride on the hip bones. Also recommended filling both flasks evenly for balance.",
    ),
    SupportTicket(
        ticket_id="T-052",
        product_id="hydration-belt",
        status="Open",
        issue_description="The zippered pocket zipper broke off completely during a trail run. My phone fell out.",
        resolution_text="",
    ),

    # ── foam-roller ──────────────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-053",
        product_id="foam-roller",
        status="Closed",
        issue_description="The EVA foam surface is cracking and flaking after 6 months of daily use. I keep it near a window.",
        resolution_text="Material degradation from UV exposure and heat affects many sports products — latex resistance bands become brittle and snap, elastic in running socks loses stretch, and silicone gaskets on hydration flask caps crack. EVA foam is particularly susceptible to UV damage when stored near windows or in direct sunlight. The ABS plastic core is still functional even with degraded foam. Recommended storing all sports equipment in a cool, dry place away from sunlight. Offered 20% discount on replacement.",
    ),
    SupportTicket(
        ticket_id="T-054",
        product_id="foam-roller",
        status="Closed",
        issue_description="I am rolling my IT band every day but it is not getting better. Am I doing it wrong?",
        resolution_text="Advised rolling the muscles surrounding the IT band (quads, glutes, hamstrings) rather than directly on the IT band itself. Direct IT band rolling can cause further irritation. Recommended 30 seconds per muscle group.",
    ),
    SupportTicket(
        ticket_id="T-055",
        product_id="foam-roller",
        status="Closed",
        issue_description="The roller makes a popping/clicking sound when I roll on it.",
        resolution_text="The ABS plastic core has internal ribs that can shift slightly under heavy load, causing noise. This does not affect function. If the core is cracked, it is a warranty issue — asked customer to send a photo.",
    ),
    SupportTicket(
        ticket_id="T-056",
        product_id="foam-roller",
        status="Open",
        issue_description="The foam roller smells like strong chemicals and is giving me a headache.",
        resolution_text="",
    ),

    # ── resistance-bands ─────────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-057",
        product_id="resistance-bands",
        status="Closed",
        issue_description="The blue (heavy) resistance band snapped during a squat exercise and hit my leg. I keep the bands in my garage near a window.",
        resolution_text="Latex degrades from UV exposure, heat, and age — the same material degradation that causes EVA foam roller surfaces to crack, running sock elastic to lose stretch, and hydration flask gaskets to fail. Bands stored near windows or in garages with temperature swings degrade much faster. Confirmed the band had visible wear marks that should have prompted replacement. Sent free replacement set and safety guidelines. Emphasized always inspecting bands for tears, discoloration, or thin spots before each use. Store all latex and rubber equipment in a cool, dry place away from direct sunlight.",
    ),
    SupportTicket(
        ticket_id="T-058",
        product_id="resistance-bands",
        status="Closed",
        issue_description="The bands keep rolling up into a tube shape during hip abduction exercises.",
        resolution_text="Suggested using a wider stance to keep the band flat. Also recommended fabric loop bands as an alternative for lower-body exercises, as they resist rolling.",
    ),
    SupportTicket(
        ticket_id="T-059",
        product_id="resistance-bands",
        status="Closed",
        issue_description="Received the set but the Yellow and Red bands seem identical in resistance.",
        resolution_text="The Yellow (extra light) and Red (light) bands have a subtle difference. Tested by stretching to 200% — Yellow should read approximately 3 lbs and Red approximately 4 lbs. If indistinguishable, it may be a mislabeled batch. Sent replacement set.",
    ),
    SupportTicket(
        ticket_id="T-060",
        product_id="resistance-bands",
        status="Open",
        issue_description="The latex smell is overwhelming. I have a latex sensitivity and my hands are breaking out in a rash.",
        resolution_text="",
    ),

    # ── garmin-forerunner-265 ────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-061",
        product_id="garmin-forerunner-265",
        status="Closed",
        issue_description="GPS takes over 2 minutes to lock on to satellites before I can start my run.",
        resolution_text="Updated firmware which refreshes satellite almanac data. Also advised starting GPS acquisition in an open area. After update, GPS locks in under 15 seconds.",
    ),
    SupportTicket(
        ticket_id="T-062",
        product_id="garmin-forerunner-265",
        status="Closed",
        issue_description="Heart rate reads 180+ BPM when I am clearly just walking.",
        resolution_text="Customer had tattoos on the wrist where the sensor sits. Optical HR sensors struggle with tattoos. Recommended wearing on the other wrist or using a Garmin HRM-Pro Plus chest strap for accurate readings.",
    ),
    SupportTicket(
        ticket_id="T-063",
        product_id="garmin-forerunner-265",
        status="Closed",
        issue_description="Battery only lasts 4 days instead of the advertised 13 days.",
        resolution_text="Customer had Always-On Display enabled, multi-band GPS, and high notification frequency. Adjusted settings: AOD off except during activities, standard GPS for training, reduced notifications. Battery now lasts 10+ days.",
    ),
    SupportTicket(
        ticket_id="T-064",
        product_id="garmin-forerunner-265",
        status="Open",
        issue_description="The watch will not sync with Garmin Connect. It has been stuck on syncing for two days.",
        resolution_text="",
    ),

    # ── rei-half-dome-tent ───────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-065",
        product_id="rei-half-dome-tent",
        status="Closed",
        issue_description="Inside of the tent was soaking wet in the morning but it did not rain overnight. My sleeping bag also felt damp.",
        resolution_text="This is condensation from breathing, not a leak — the rainfly's 1500mm polyurethane coating and factory-taped seams are intact. Condensation can make sleeping bags damp, which is particularly problematic for the Kelty Cosmic down fill (down clumps when wet, even with DriDown treatment). The NEMO Disco synthetic fill handles moisture better than down. Advised opening both vestibule doors partially and the ceiling vent for airflow. Keep sleeping bags in a waterproof stuff sack or dry bag inside the tent as an extra precaution.",
    ),
    SupportTicket(
        ticket_id="T-066",
        product_id="rei-half-dome-tent",
        status="Closed",
        issue_description="The fabric sleeve where the pole goes in ripped when I was setting up the tent.",
        resolution_text="Customer was forcing a bent pole section. Applied Tenacious Tape as field repair. Processed warranty claim for permanent repair at REI store.",
    ),
    SupportTicket(
        ticket_id="T-067",
        product_id="rei-half-dome-tent",
        status="Closed",
        issue_description="The tent has a strong mildew smell. I stored it in my garage over winter.",
        resolution_text="Customer stored the tent damp after last trip. Mildew voids warranty but advised washing with enzyme-based cleaner and drying thoroughly in shade. Emphasized never storing a wet tent.",
    ),
    SupportTicket(
        ticket_id="T-068",
        product_id="rei-half-dome-tent",
        status="Open",
        issue_description="Water is leaking through the floor seams during heavy rain even though the tent is brand new.",
        resolution_text="",
    ),

    # ── nemo-disco-sleeping-bag ──────────────────────────────────────────
    SupportTicket(
        ticket_id="T-069",
        product_id="nemo-disco-sleeping-bag",
        status="Closed",
        issue_description="The sleeping bag does not keep me warm at 35°F. The 30°F rating seems misleading.",
        resolution_text="Explained that the 30°F is a lower limit, not a comfort rating. Comfortable use is above 40°F. Recommended pairing with a sleeping pad with R-value 3+ for ground insulation. Suggested a bag liner for extra warmth.",
    ),
    SupportTicket(
        ticket_id="T-070",
        product_id="nemo-disco-sleeping-bag",
        status="Closed",
        issue_description="The main zipper keeps getting stuck on the fabric inside the bag.",
        resolution_text="Advised holding the draft tube fabric flat with one hand while zipping. Applied zipper wax to the slider. If slider is bent, gently reshape with pliers.",
    ),
    SupportTicket(
        ticket_id="T-071",
        product_id="nemo-disco-sleeping-bag",
        status="Closed",
        issue_description="The synthetic fill feels much thinner than when I bought it. The bag is not as puffy.",
        resolution_text="Customer had been storing in the stuff sack for 6 months. Advised washing with tech cleaner and tumble drying low to restore loft. Emphasized storing in the oversized cotton sack.",
    ),
    SupportTicket(
        ticket_id="T-072",
        product_id="nemo-disco-sleeping-bag",
        status="Open",
        issue_description="The zipper pull broke off completely. Now I cannot open or close the bag.",
        resolution_text="",
    ),

    # ── msr-hubba-hubba-tent ─────────────────────────────────────────────
    SupportTicket(
        ticket_id="T-073",
        product_id="msr-hubba-hubba-tent",
        status="Closed",
        issue_description="Water is pooling on top of the rainfly during rain. It is sagging badly.",
        resolution_text="Advised tightening corner buckles and staking out all guylines to create even tension. Checked for bent pole sections which can cause sag.",
    ),
    SupportTicket(
        ticket_id="T-074",
        product_id="msr-hubba-hubba-tent",
        status="Closed",
        issue_description="The central pole hub connector cracked while setting up in cold weather.",
        resolution_text="Cold temperatures can make plastic hubs brittle. Shipped replacement hub connector. Advised warming poles in hands before assembly in sub-freezing conditions.",
    ),
    SupportTicket(
        ticket_id="T-075",
        product_id="msr-hubba-hubba-tent",
        status="Closed",
        issue_description="One of the tent stakes bent on the first use in rocky ground.",
        resolution_text="The included aluminum stakes are lightweight but not designed for rocky soil. Recommended MSR Groundhog stakes for hard ground. Sent replacement stakes.",
    ),
    SupportTicket(
        ticket_id="T-076",
        product_id="msr-hubba-hubba-tent",
        status="Open",
        issue_description="The rainfly zipper on the vestibule is completely jammed and will not move in either direction.",
        resolution_text="",
    ),

    # ── kelty-cosmic-sleeping-bag ────────────────────────────────────────
    SupportTicket(
        ticket_id="T-077",
        product_id="kelty-cosmic-sleeping-bag",
        status="Closed",
        issue_description="The down fill has clumped into balls after the bag got wet during a storm. The DriDown treatment did not seem to help at all — the 550-fill down collapsed immediately.",
        resolution_text="DriDown is a hydrophobic treatment that helps in light humidity but is not waterproof. In a full soaking, down fill clumps regardless. This insulation loft loss from moisture is similar to how the NEMO Disco synthetic fill loses loft when stored compressed — both require the same tennis ball dryer method to restore. Advised tumble drying on low with 2-3 clean tennis balls for 60-90 minutes — the tennis balls break apart clumps and redistribute fill. Do not air-dry down bags as the slow drying risks mildew. For future trips, keep the bag in a waterproof dry bag inside the tent. The REI Half Dome tent's rainfly is rated at 1500mm but condensation can still dampen gear inside.",
    ),
    SupportTicket(
        ticket_id="T-078",
        product_id="kelty-cosmic-sleeping-bag",
        status="Closed",
        issue_description="Small feathers keep poking through the shell fabric and sticking me at night.",
        resolution_text="Explained feather migration is normal for down bags. Advised pushing feathers back in from outside rather than pulling them out. Pulling enlarges holes. A small amount of migration does not affect warmth.",
    ),
    SupportTicket(
        ticket_id="T-079",
        product_id="kelty-cosmic-sleeping-bag",
        status="Closed",
        issue_description="I washed the sleeping bag in a top-loader and now the baffles look weird.",
        resolution_text="Top-loading agitators can damage baffle stitching. Advised only using front-loading washers for down bags. Tumble dried low with tennis balls to redistribute fill. If baffles are torn, warranty replacement is available.",
    ),
    SupportTicket(
        ticket_id="T-080",
        product_id="kelty-cosmic-sleeping-bag",
        status="Open",
        issue_description="The DriDown treatment does not seem to be working. My bag got damp from condensation and the down collapsed immediately.",
        resolution_text="",
    ),

    # ── therm-a-rest-sleeping-pad ────────────────────────────────────────
    SupportTicket(
        ticket_id="T-081",
        product_id="therm-a-rest-sleeping-pad",
        status="Closed",
        issue_description="My pad is almost completely flat by morning. I inflate it fully before bed.",
        resolution_text="Temperature drops cause air contraction (minor deflation is normal). Tested for leak by submerging in water — found a pinhole near a seam. Applied included repair patch. Pad now holds air through the night.",
    ),
    SupportTicket(
        ticket_id="T-082",
        product_id="therm-a-rest-sleeping-pad",
        status="Closed",
        issue_description="Air keeps hissing from the valve even when I close it completely.",
        resolution_text="Found sand grains in the valve mechanism. Rinsed valve under clean water while opening and closing several times. Debris cleared and valve now seals properly.",
    ),
    SupportTicket(
        ticket_id="T-083",
        product_id="therm-a-rest-sleeping-pad",
        status="Closed",
        issue_description="I inflated the pad by blowing into it and now there is moisture visible inside.",
        resolution_text="Moisture from breath degrades the internal Triangular Core Matrix and reflective layers. Advised always using the included pump sack. Dried pad by leaving valve open in low humidity for 48 hours. Emphasized pump sack use going forward.",
    ),
    SupportTicket(
        ticket_id="T-084",
        product_id="therm-a-rest-sleeping-pad",
        status="Open",
        issue_description="The pad developed a large bubble on one side where the internal baffles seem to have separated.",
        resolution_text="",
    ),
]


# ---------------------------------------------------------------------------
# Reviews  (84 total — 4 per product)
# ---------------------------------------------------------------------------

REVIEWS: list[Review] = [
    # ── nike-pegasus-40 ───────────────────────────────────────────────────
    Review(review_id="R-001", product_id="nike-pegasus-40", rating=5, date="2024-03-15", raw_text="Best daily trainer I have ever owned. The React foam is incredibly responsive and I can run in these every day without my legs feeling beat up."),
    Review(review_id="R-002", product_id="nike-pegasus-40", rating=4, date="2024-04-20", raw_text="Great shoe overall but runs a bit narrow in the midfoot. Had to go with the wide version. Once I did, they are perfect for my 30-mile weeks."),
    Review(review_id="R-003", product_id="nike-pegasus-40", rating=2, date="2024-05-10", raw_text="The React foam cushion went flat after only 250 miles. My previous Pegasus 39 lasted much longer. I switched to the Adidas Ultraboost and its Boost midsole seems to hold up better, though it is heavier."),
    Review(review_id="R-004", product_id="nike-pegasus-40", rating=3, date="2024-06-01", raw_text="Decent shoe but I got heel blisters for the first two weeks. After switching my lacing technique it got better. Not ideal out of the box."),

    # ── adidas-ultraboost-24 ──────────────────────────────────────────────
    Review(review_id="R-005", product_id="adidas-ultraboost-24", rating=5, date="2024-03-22", raw_text="The Boost midsole is unreal. Like running on clouds with energy return. Worth every penny of the $190 price tag."),
    Review(review_id="R-006", product_id="adidas-ultraboost-24", rating=3, date="2024-05-05", raw_text="Great cushion but the Boost foam yellowed within two months. Same yellowing issue I had with my Air Max 90 midsole. The baking soda and hydrogen peroxide paste fix works on both but I should not have to clean premium shoes constantly."),
    Review(review_id="R-007", product_id="adidas-ultraboost-24", rating=1, date="2024-06-18", raw_text="The Continental rubber outsole started peeling from the Boost midsole after just 3 months. Outsole separation is a deal breaker. My friend had the same delamination issue on his Nike Pegasus. I stopped running in them and contacted support for a warranty review."),
    Review(review_id="R-008", product_id="adidas-ultraboost-24", rating=4, date="2024-07-10", raw_text="Heavy for a running shoe at 310g but the comfort makes up for it. I use these for easy recovery runs."),

    # ── nb-990v6 ──────────────────────────────────────────────────────────
    Review(review_id="R-009", product_id="nb-990v6", rating=5, date="2024-04-01", raw_text="Made in USA quality you can feel. The pigskin suede and mesh upper is beautiful. Worth every cent of $200."),
    Review(review_id="R-010", product_id="nb-990v6", rating=4, date="2024-05-15", raw_text="Classic look and solid construction. Takes a while to break in — the ENCAP midsole is firm at first, much stiffer than the React foam in my Pegasus or the Boost in my Ultraboost. After 30 miles it feels great. Similar break-in to the Stan Smith leather."),
    Review(review_id="R-011", product_id="nb-990v6", rating=2, date="2024-06-20", raw_text="Got caught in rain once and the pigskin suede is permanently water-stained. Same thing happened to my 574s. Unlike the DriDown treatment on my Kelty sleeping bag, there is zero water resistance on these suede panels. For $200 I expected at least a suede protector spray included in the box."),
    Review(review_id="R-012", product_id="nb-990v6", rating=3, date="2024-07-08", raw_text="Good shoe but noticeably heavier than other running shoes at 340g. More of a lifestyle shoe that happens to run okay."),

    # ── asics-gel-nimbus-26 ───────────────────────────────────────────────
    Review(review_id="R-013", product_id="asics-gel-nimbus-26", rating=5, date="2024-04-10", raw_text="Maximum cushion heaven. The FF Blast Plus midsole is softer than both the Nike Pegasus React foam and the Adidas Ultraboost Boost. My knees thank me. Rotating between these and the Brooks Ghost 16 with DNA Loft v2 for daily training."),
    Review(review_id="R-014", product_id="asics-gel-nimbus-26", rating=4, date="2024-05-25", raw_text="Super plush ride but it is a neutral shoe — no pronation support. Make sure you know your gait before buying."),
    Review(review_id="R-015", product_id="asics-gel-nimbus-26", rating=2, date="2024-07-02", raw_text="The mesh tore at the toe box after 2 months. I think my toenails caused it but still, it should be more durable."),
    Review(review_id="R-016", product_id="asics-gel-nimbus-26", rating=1, date="2024-08-15", raw_text="Felt a hard lump under my heel from day one. The PureGEL insert was deformed. Had to return."),

    # ── brooks-ghost-16 ──────────────────────────────────────────────────
    Review(review_id="R-017", product_id="brooks-ghost-16", rating=5, date="2024-03-30", raw_text="The smoothest ride in a neutral shoe. The DNA Loft v2 midsole is soft without being mushy — softer than the New Balance ENCAP but firmer than the ASICS FF Blast Plus. My go-to daily trainer. Rotating with the Nike Pegasus for variety."),
    Review(review_id="R-018", product_id="brooks-ghost-16", rating=4, date="2024-05-20", raw_text="Reliable and comfortable but nothing flashy. Does everything well. The outsole wears evenly and lasts a long time."),
    Review(review_id="R-019", product_id="brooks-ghost-16", rating=2, date="2024-06-30", raw_text="Annoying squeaking noise from the insole. Had to put baby powder in the shoe to stop it. Should not happen with a $140 shoe."),
    Review(review_id="R-020", product_id="brooks-ghost-16", rating=3, date="2024-08-05", raw_text="Good shoe but not enough arch support for my flat feet. I need something with a medial post. Switching to the Adrenaline."),

    # ── nike-air-max-90 ──────────────────────────────────────────────────
    Review(review_id="R-021", product_id="nike-air-max-90", rating=5, date="2024-04-15", raw_text="A timeless classic. The visible Air unit is iconic. I get compliments every time I wear these."),
    Review(review_id="R-022", product_id="nike-air-max-90", rating=4, date="2024-06-10", raw_text="Great lifestyle shoe. Just do not try to run in them — they are heavy and the Air unit is not designed for it."),
    Review(review_id="R-023", product_id="nike-air-max-90", rating=2, date="2024-07-25", raw_text="The Air bubble deflated on one shoe after a year. Shoe looks lopsided now. Nike says it is out of warranty."),
    Review(review_id="R-024", product_id="nike-air-max-90", rating=3, date="2024-09-01", raw_text="Love the design but the white midsole yellows fast — same oxidation problem as my Ultraboost Boost foam. The baking soda and hydrogen peroxide paste works on both but I should not have to clean shoes every month. Even my Stan Smiths are starting to yellow at the rubber midsole."),

    # ── adidas-stan-smith ────────────────────────────────────────────────
    Review(review_id="R-025", product_id="adidas-stan-smith", rating=5, date="2024-03-20", raw_text="Minimalist perfection. Goes with everything. The leather ages beautifully if you take care of it."),
    Review(review_id="R-026", product_id="adidas-stan-smith", rating=3, date="2024-05-12", raw_text="The full-grain leather is very stiff out of the box. Took a full week of painful break-in before they were comfortable. Reminds me of the break-in on my 990v6 ENCAP midsole, which needed about 30 miles. Different materials but the same patience required."),
    Review(review_id="R-027", product_id="adidas-stan-smith", rating=2, date="2024-07-15", raw_text="The leather started cracking badly across the toe after 4 months. Should have conditioned it sooner I guess."),
    Review(review_id="R-028", product_id="adidas-stan-smith", rating=4, date="2024-08-20", raw_text="Classic shoe that never goes out of style. The green heel tab is a nice touch. Just remember to condition the leather."),

    # ── nb-574 ────────────────────────────────────────────────────────────
    Review(review_id="R-029", product_id="nb-574", rating=5, date="2024-04-05", raw_text="The perfect retro sneaker. Suede and mesh combo looks great. ENCAP cushion is comfortable for all-day wear."),
    Review(review_id="R-030", product_id="nb-574", rating=4, date="2024-06-15", raw_text="Great shoe but wish it came in wider options by default. Had to order the 2E width. Once I did, perfect fit."),
    Review(review_id="R-031", product_id="nb-574", rating=2, date="2024-07-28", raw_text="The suede panels stain so easily from water. Got caught in rain once and now they look terrible. My 990v6 pigskin suede had the same water damage problem. Neither shoe has any water resistance — unlike my Kelty sleeping bag DriDown or my tent rainfly. A suede protector spray is essential but should come included at this price."),
    Review(review_id="R-032", product_id="nb-574", rating=3, date="2024-09-10", raw_text="Good casual shoe but the insole slides around and bunches up under the arch. Had to use double-sided tape to keep it in place — same fix I used on my ASICS Nimbus 26 OrthoLite insole. Seems like removable insoles are problematic across brands. My Brooks Ghost 16 insole squeaks too."),

    # ── nike-drifit-tee ──────────────────────────────────────────────────
    Review(review_id="R-033", product_id="nike-drifit-tee", rating=5, date="2024-04-12", raw_text="Dri-FIT technology really works. Even on hot summer runs the shirt keeps me dry. Lightweight and breathable."),
    Review(review_id="R-034", product_id="nike-drifit-tee", rating=3, date="2024-06-22", raw_text="The Dri-FIT moisture wicking stopped working after a few months. Turns out fabric softener kills it — same thing happened to my Adidas AEROREADY running shorts. A white vinegar wash restored the wicking on both. Never use fabric softener on any moisture-wicking apparel."),
    Review(review_id="R-035", product_id="nike-drifit-tee", rating=2, date="2024-08-01", raw_text="The Dri-FIT shirt pills like crazy after just 5 washes. The synthetic polyester fabric also retains odor even after washing — same odor problem I noticed with my AEROREADY shorts liner. For $35 I expected better fabric quality. At least a vinegar soak helps with the smell."),
    Review(review_id="R-036", product_id="nike-drifit-tee", rating=4, date="2024-09-15", raw_text="Great performance shirt. Just do not use fabric softener and wash it inside out. Holds up well when you follow the care instructions."),

    # ── adidas-running-shorts ────────────────────────────────────────────
    Review(review_id="R-037", product_id="adidas-running-shorts", rating=5, date="2024-05-01", raw_text="AEROREADY fabric dries so fast. The 5-inch inseam is perfect and the built-in liner is comfortable."),
    Review(review_id="R-038", product_id="adidas-running-shorts", rating=3, date="2024-06-28", raw_text="Good shorts but the liner chafes on anything over 10 miles. Need to use Body Glide with these."),
    Review(review_id="R-039", product_id="adidas-running-shorts", rating=2, date="2024-08-12", raw_text="The drawstring pulled inside the waistband on the first wash. Very annoying to thread back through."),
    Review(review_id="R-040", product_id="adidas-running-shorts", rating=4, date="2024-09-20", raw_text="Love the recycled polyester material. Feels good knowing it is sustainable. Comfortable for runs up to half marathon distance."),

    # ── ua-coldgear ──────────────────────────────────────────────────────
    Review(review_id="R-041", product_id="ua-coldgear", rating=5, date="2024-01-15", raw_text="Game changer for winter running. The brushed interior is incredibly warm without any bulk. Best base layer I have owned."),
    Review(review_id="R-042", product_id="ua-coldgear", rating=4, date="2024-02-20", raw_text="Keeps me warm down to about 30°F with a wind layer on top. The ColdGear compression fit takes getting used to — similar to the break-in stiffness on my Stan Smiths, just a different kind of discomfort. The moisture wicking works great as long as you never use fabric softener, same as Dri-FIT and AEROREADY."),
    Review(review_id="R-043", product_id="ua-coldgear", rating=2, date="2024-03-10", raw_text="Shrunk a full size after one wash. I followed the care label. Very frustrating. Had to buy a new one in a size up."),
    Review(review_id="R-044", product_id="ua-coldgear", rating=3, date="2024-11-05", raw_text="Good warmth but the shoulder seam started coming apart after 3 months. Warranty replaced it but still concerning quality."),

    # ── nike-running-socks ───────────────────────────────────────────────
    Review(review_id="R-045", product_id="nike-running-socks", rating=5, date="2024-04-18", raw_text="Cushioning is perfect. The arch band provides great support and Dri-FIT keeps my feet dry. Best running socks at this price."),
    Review(review_id="R-046", product_id="nike-running-socks", rating=4, date="2024-06-05", raw_text="Good quality 2-pack. Love that they are left and right specific. Just make sure you get the right size — they run slightly large."),
    Review(review_id="R-047", product_id="nike-running-socks", rating=2, date="2024-08-15", raw_text="The elastic arch band stretched out after 4 months. The Dri-FIT wicking still works but the socks slide around in my shoes now. Elastic degradation seems to be a problem with lots of sports gear — my resistance bands lost their stretch too, and the gasket on my hydration flask cap cracked. Wash cold to extend elastic life."),
    Review(review_id="R-048", product_id="nike-running-socks", rating=3, date="2024-09-30", raw_text="Decent socks but the toe seam is slightly raised and I can feel it when running. Causes minor irritation on long runs."),

    # ── hydration-belt ───────────────────────────────────────────────────
    Review(review_id="R-049", product_id="hydration-belt", rating=5, date="2024-05-10", raw_text="Perfect for long runs. Two 10oz flasks is enough for up to 15 miles. The zippered pocket holds my phone securely."),
    Review(review_id="R-050", product_id="hydration-belt", rating=3, date="2024-07-20", raw_text="Belt works well but one flask cap leaked from day one. Had to tighten it really hard to stop the dripping."),
    Review(review_id="R-051", product_id="hydration-belt", rating=2, date="2024-08-25", raw_text="Bounces way too much when running. Could not find a good position on my hips. Switched to a handheld bottle instead."),
    Review(review_id="R-052", product_id="hydration-belt", rating=1, date="2024-09-12", raw_text="Flasks developed a mildew smell within a month even though I rinse them. Odor retention seems to plague all my synthetic gear — my Dri-FIT shirts hold smell too, and my AEROREADY shorts liner. Baking soda soak helps the flasks but vinegar works better on apparel. Switched to a vest system."),

    # ── foam-roller ──────────────────────────────────────────────────────
    Review(review_id="R-053", product_id="foam-roller", rating=5, date="2024-03-25", raw_text="The GRID surface is genius. Different density zones target different muscle groups. Essential recovery tool after hard runs."),
    Review(review_id="R-054", product_id="foam-roller", rating=4, date="2024-05-30", raw_text="Solid construction with the ABS core. More durable than cheaper foam rollers. The 13-inch length is portable too."),
    Review(review_id="R-055", product_id="foam-roller", rating=3, date="2024-07-15", raw_text="Works well but the EVA foam surface started cracking after 6 months of daily use. I kept it near a sunny window which probably accelerated the degradation. Same UV damage issue that killed my resistance bands and wore out the elastic in my running socks faster. Store all this stuff away from sunlight."),
    Review(review_id="R-056", product_id="foam-roller", rating=2, date="2024-09-05", raw_text="Strong chemical smell out of the box. Had to leave it outside for a week before I could use it indoors."),

    # ── resistance-bands ─────────────────────────────────────────────────
    Review(review_id="R-057", product_id="resistance-bands", rating=5, date="2024-04-08", raw_text="Great set of 5 progressive resistance levels. Perfect for physical therapy exercises and warm-ups before runs."),
    Review(review_id="R-058", product_id="resistance-bands", rating=4, date="2024-06-12", raw_text="Good quality latex bands. The color coding makes it easy to progress through resistance levels. Store them away from heat."),
    Review(review_id="R-059", product_id="resistance-bands", rating=2, date="2024-08-20", raw_text="The heavy blue latex band snapped during a squat and left a welt on my leg. I stored the bands in my garage near a window — UV and heat degrade latex just like they crack EVA foam on my foam roller and wear out the elastic in my running socks. Always inspect bands for tears, thin spots, or discoloration before each use. Store in a cool dark place."),
    Review(review_id="R-060", product_id="resistance-bands", rating=3, date="2024-10-01", raw_text="The flat bands keep rolling up into a tube during leg exercises. Annoying. Fabric bands would be better for lower body."),

    # ── garmin-forerunner-265 ────────────────────────────────────────────
    Review(review_id="R-061", product_id="garmin-forerunner-265", rating=5, date="2024-02-14", raw_text="The AMOLED display is stunning. Training metrics are incredibly detailed — VO2 max, training status, recovery time. Best running watch at this price."),
    Review(review_id="R-062", product_id="garmin-forerunner-265", rating=4, date="2024-04-22", raw_text="Excellent GPS accuracy with multi-band mode. Battery life is good at 13 days in smartwatch mode but only 20 hours in GPS mode."),
    Review(review_id="R-063", product_id="garmin-forerunner-265", rating=2, date="2024-06-30", raw_text="Heart rate sensor is wildly inaccurate. Shows 180 BPM when I am just walking. Turns out my wrist tattoos interfere with it."),
    Review(review_id="R-064", product_id="garmin-forerunner-265", rating=3, date="2024-08-10", raw_text="Good watch but GPS takes forever to lock on. Sometimes I wait 3 minutes standing outside before I can start my run."),

    # ── rei-half-dome-tent ───────────────────────────────────────────────
    Review(review_id="R-065", product_id="rei-half-dome-tent", rating=5, date="2024-05-15", raw_text="Held up perfectly in heavy rain on the Appalachian Trail. Color-coded poles made setup easy even in fading light."),
    Review(review_id="R-066", product_id="rei-half-dome-tent", rating=4, date="2024-07-01", raw_text="Roomy for two people with gear. A bit heavy for ultralight backpacking at 1.64kg but the livability is worth it."),
    Review(review_id="R-067", product_id="rei-half-dome-tent", rating=2, date="2024-08-18", raw_text="Tons of condensation on the inner tent walls every morning even with the 1500mm PU rainfly coating keeping rain out. My Kelty Cosmic down sleeping bag got damp from the condensation and the DriDown fill clumped. Opening vents helps but does not eliminate it. Keep your sleeping bag in a waterproof dry bag inside the tent."),
    Review(review_id="R-068", product_id="rei-half-dome-tent", rating=3, date="2024-09-25", raw_text="Good tent overall but the pole sleeve ripped on my second trip. Tenacious Tape fixed it but should not happen on a new tent."),

    # ── nemo-disco-sleeping-bag ──────────────────────────────────────────
    Review(review_id="R-069", product_id="nemo-disco-sleeping-bag", rating=5, date="2024-04-20", raw_text="The spoon shape is a game changer for side sleepers. Finally a bag where my knees and elbows are not constricted. So comfortable."),
    Review(review_id="R-070", product_id="nemo-disco-sleeping-bag", rating=4, date="2024-06-10", raw_text="Warm and comfortable but heavier than down alternatives at 1.13kg. Worth the trade-off for synthetic since it handles moisture better."),
    Review(review_id="R-071", product_id="nemo-disco-sleeping-bag", rating=2, date="2024-08-05", raw_text="The 30-degree rating is optimistic. I was freezing at 38°F even with the Therm-a-Rest NeoAir XTherm pad underneath (R-value 6.9). The synthetic insulation loses loft faster than the Kelty Cosmic down fill. Need a much warmer bag or at minimum a liner."),
    Review(review_id="R-072", product_id="nemo-disco-sleeping-bag", rating=3, date="2024-09-15", raw_text="Good bag but the zipper catches on the draft tube every single time. Very frustrating when you are trying to get in and out at night."),

    # ── msr-hubba-hubba-tent ─────────────────────────────────────────────
    Review(review_id="R-073", product_id="msr-hubba-hubba-tent", rating=5, date="2024-05-05", raw_text="Ultralight perfection at 1.54kg. Two doors, two vestibules, symmetrical design. Sets up in under 5 minutes. Worth every penny."),
    Review(review_id="R-074", product_id="msr-hubba-hubba-tent", rating=4, date="2024-07-12", raw_text="Excellent tent but the stakes that come with it are flimsy. Immediately upgraded to MSR Groundhog stakes for rocky terrain."),
    Review(review_id="R-075", product_id="msr-hubba-hubba-tent", rating=2, date="2024-08-28", raw_text="The rainfly pools water on top in heavy rain. Have to get out and re-tension the guylines. Design flaw for a $450 tent."),
    Review(review_id="R-076", product_id="msr-hubba-hubba-tent", rating=3, date="2024-10-05", raw_text="Good tent overall but the pole hub cracked in cold weather on a fall camping trip. MSR sent a replacement but it was stressful in the field."),

    # ── kelty-cosmic-sleeping-bag ────────────────────────────────────────
    Review(review_id="R-077", product_id="kelty-cosmic-sleeping-bag", rating=5, date="2024-04-25", raw_text="Best value down sleeping bag on the market. DriDown treatment and 550-fill for only $130. Warm and comfortable to 25°F."),
    Review(review_id="R-078", product_id="kelty-cosmic-sleeping-bag", rating=4, date="2024-06-20", raw_text="Great budget option. Slightly heavier than premium down bags at 1.36kg but the warmth-to-price ratio is unbeatable."),
    Review(review_id="R-079", product_id="kelty-cosmic-sleeping-bag", rating=2, date="2024-08-10", raw_text="Got the 550-fill DriDown wet from tent condensation and the down clumped badly. DriDown is supposed to repel moisture but it clearly has limits — unlike the REI Half Dome tent rainfly which has real waterproof coating. Tennis balls in the dryer on low heat fixed the clumping but it took hours. The NEMO Disco synthetic fill handles moisture much better than down."),
    Review(review_id="R-080", product_id="kelty-cosmic-sleeping-bag", rating=3, date="2024-09-30", raw_text="Feathers keep poking through the shell fabric. Not a huge deal for warmth but it is annoying and feels cheap."),

    # ── therm-a-rest-sleeping-pad ────────────────────────────────────────
    Review(review_id="R-081", product_id="therm-a-rest-sleeping-pad", rating=5, date="2024-03-18", raw_text="R-value of 6.9 is no joke. Slept warm on snow in January. The NeoAir XTherm is the gold standard for 4-season sleeping pads."),
    Review(review_id="R-082", product_id="therm-a-rest-sleeping-pad", rating=4, date="2024-05-22", raw_text="Incredibly warm and lightweight at 430g. The pump sack works well. Just be careful with the valve — sand can jam it."),
    Review(review_id="R-083", product_id="therm-a-rest-sleeping-pad", rating=2, date="2024-07-30", raw_text="Woke up on the ground. Pad deflated overnight from a pinhole leak. For $230 I expected better durability. At least the repair kit works."),
    Review(review_id="R-084", product_id="therm-a-rest-sleeping-pad", rating=3, date="2024-09-08", raw_text="Good pad but crinkly and noisy when you move around. Sounds like a chip bag. Light sleepers beware."),
]


# ---------------------------------------------------------------------------
# Runtime validation — ensure all product_id values exist in the catalog
# ---------------------------------------------------------------------------

def _validate_product_refs() -> None:
    """Check all articles, tickets, and reviews reference valid product IDs."""
    for article in KNOWLEDGE_ARTICLES:
        if article.product_id not in _VALID_PRODUCT_IDS:
            raise ValueError(
                f"KnowledgeArticle {article.article_id} references unknown product "
                f"{article.product_id!r}"
            )
    for ticket in SUPPORT_TICKETS:
        if ticket.product_id not in _VALID_PRODUCT_IDS:
            raise ValueError(
                f"SupportTicket {ticket.ticket_id} references unknown product "
                f"{ticket.product_id!r}"
            )
    for review in REVIEWS:
        if review.product_id not in _VALID_PRODUCT_IDS:
            raise ValueError(
                f"Review {review.review_id} references unknown product "
                f"{review.product_id!r}"
            )


_validate_product_refs()
