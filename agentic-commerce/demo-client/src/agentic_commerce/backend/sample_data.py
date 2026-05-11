from __future__ import annotations

from .models import (
    AgenticSearchOut,
    CitedSource,
    DemoWarning,
    DiagnosisPathStep,
    GraphHop,
    IssueDiagnosisOut,
    KnowledgeChunk,
    MemoryWrite,
    ProductCard,
    ProfileChip,
    RecommendedAction,
    SourceType,
    TimingMetadata,
    ToolTimelineItem,
)


SEARCH_PRESETS = {
    "trail-running-shoes": {
        "answer": (
            "For waterproof trail running under $150, start with the Brooks "
            "Cascadia 17 GTX. It balances wet-weather protection, trail grip, "
            "and enough cushioning for rocky weekend runs."
        ),
        "summary": "Ranked waterproof trail running shoes under $150.",
        "products": [
            ProductCard(
                id="sample-brooks-cascadia-17-gtx",
                name="Cascadia 17 GTX",
                brand="Brooks",
                category="Trail running shoes",
                price=149.0,
                in_stock=True,
                score=0.94,
                rationale="Best balance of waterproofing, grip, and under-$150 pricing.",
                signals=["waterproof", "trail grip", "under $150", "stable"],
            ),
            ProductCard(
                id="sample-pegasus-trail-4",
                name="Pegasus Trail 4 GTX",
                brand="Nike",
                category="Trail running shoes",
                price=140.0,
                in_stock=True,
                score=0.88,
                rationale="Lighter road-to-trail option with weather protection.",
                signals=["waterproof", "road-to-trail", "lightweight"],
            ),
        ],
    },
    "rain-hiking-jacket": {
        "answer": (
            "For a light hiking shell that can handle rain, pick the Stormline "
            "Stretch Rain Shell. It packs small, breathes well, and keeps a "
            "clean feature set for day hikes."
        ),
        "summary": "Ranked lightweight rain shells for day hikes.",
        "products": [
            ProductCard(
                id="sample-stormline-shell",
                name="Stormline Stretch Rain Shell",
                brand="Black Diamond",
                category="Rain jacket",
                price=169.0,
                in_stock=True,
                score=0.91,
                rationale="Strong packability and stretch without overbuilding.",
                signals=["waterproof", "packable", "stretch", "day hike"],
            ),
            ProductCard(
                id="sample-patagonia-torrentshell",
                name="Torrentshell 3L",
                brand="Patagonia",
                category="Rain jacket",
                price=179.0,
                in_stock=True,
                score=0.87,
                rationale="More durable three-layer shell for wetter hikes.",
                signals=["waterproof", "durable", "3-layer"],
            ),
        ],
    },
    "cold-weather-layers": {
        "answer": (
            "For cold-weather running, start with the Under Armour ColdGear "
            "Base Layer, add a Nike Dri-FIT shirt when you need another "
            "moisture-moving layer, and use Dri-FIT socks to keep the system "
            "consistent."
        ),
        "summary": "Built a cold-weather running kit around moisture-wicking layers.",
        "products": [
            ProductCard(
                id="ua-coldgear",
                name="Under Armour ColdGear Base Layer",
                brand="Under Armour",
                category="Apparel",
                price=55.0,
                in_stock=True,
                score=0.92,
                rationale="Warm compression base layer for cold-weather running.",
                signals=["ColdGear", "compression", "winter running"],
            ),
            ProductCard(
                id="nike-drifit-tee",
                name="Nike Dri-FIT Running Shirt",
                brand="Nike",
                category="Apparel",
                price=35.0,
                in_stock=True,
                score=0.86,
                rationale="Light moisture-wicking layer that pairs well with the base layer.",
                signals=["Dri-FIT", "moisture wicking", "polyester"],
            ),
            ProductCard(
                id="nike-running-socks",
                name="Nike Multiplier Running Socks (2-Pack)",
                brand="Nike",
                category="Accessories",
                price=18.0,
                in_stock=True,
                score=0.8,
                rationale="Cushioned Dri-FIT socks complete the cold-weather running setup.",
                signals=["Dri-FIT", "arch support", "cushioned"],
            ),
        ],
    },
    "backpacking-tent-comparison": {
        "answer": (
            "The REI Half Dome SL 2+ is the value and livability pick, while "
            "the MSR Hubba Hubba NX 2 is the lighter premium backpacking tent."
        ),
        "summary": "Compared two 2-person backpacking tents on price, weight, and field notes.",
        "products": [
            ProductCard(
                id="rei-half-dome-tent",
                name="REI Co-op Half Dome SL 2+ Tent",
                brand="REI Co-op",
                category="Outdoor Equipment",
                price=279.0,
                in_stock=True,
                score=0.9,
                rationale="Better value for a roomy two-person backpacking shelter.",
                signals=["$279", "roomy", "3-season"],
            ),
            ProductCard(
                id="msr-hubba-hubba-tent",
                name="MSR Hubba Hubba NX 2 Tent",
                brand="MSR",
                category="Outdoor Equipment",
                price=450.0,
                in_stock=True,
                score=0.86,
                rationale="Better for weight-conscious backpackers who want a premium tent.",
                signals=["1.54kg", "two vestibules", "premium"],
            ),
        ],
    },
    "two-person-backpacking-setup": {
        "answer": (
            "A balanced 2-person setup under $750 is the REI Half Dome SL 2+ "
            "Tent, Kelty Cosmic 20 Down Sleeping Bag, and Therm-a-Rest NeoAir "
            "XTherm Sleeping Pad. The sample total is $638.90."
        ),
        "summary": "Built a tent, sleeping bag, and pad bundle under $750.",
        "products": [
            ProductCard(
                id="rei-half-dome-tent",
                name="REI Co-op Half Dome SL 2+ Tent",
                brand="REI Co-op",
                category="Outdoor Equipment",
                price=279.0,
                in_stock=True,
                score=0.91,
                rationale="Controls shelter cost while keeping a roomy two-person tent.",
                signals=["2-person", "$279", "3-season"],
            ),
            ProductCard(
                id="kelty-cosmic-sleeping-bag",
                name="Kelty Cosmic 20 Down Sleeping Bag",
                brand="Kelty",
                category="Outdoor Equipment",
                price=129.95,
                in_stock=True,
                score=0.87,
                rationale="Budget 20F down bag that keeps the bundle below the cap.",
                signals=["20F", "$129.95", "550-fill down"],
            ),
            ProductCard(
                id="therm-a-rest-sleeping-pad",
                name="Therm-a-Rest NeoAir XTherm Sleeping Pad",
                brand="Therm-a-Rest",
                category="Outdoor Equipment",
                price=229.95,
                in_stock=True,
                score=0.84,
                rationale="High R-value pad for warmth without breaking the bundle budget.",
                signals=["R-value 6.9", "$229.95", "4-season"],
            ),
        ],
    },
}


DIAGNOSIS_PRESETS = {
    "running-shoes-feel-flat": {
        "answer": (
            "Running shoes that feel flat after about 300 miles usually have "
            "compressed midsole foam. Rotate in a fresh pair, check outsole "
            "wear, and reserve the old pair for short easy runs if traction is safe."
        ),
        "summary": "Flat ride points to midsole compression after high mileage.",
        "symptom": "Running shoes feel flat and unresponsive after 300 miles.",
        "solution": "Replace or rotate the shoes and inspect outsole traction.",
    },
    "outsole-peeling": {
        "answer": (
            "Outsole peeling after a few months is usually an adhesion or flex "
            "stress issue. Stop running in the shoe if the tread is lifting, "
            "keep it away from heat, and contact support for a warranty review. "
            "For a small separation, a shoe-specific adhesive can work as a "
            "temporary repair."
        ),
        "summary": "Peeling outsole suggests adhesion failure or high-flex wear.",
        "symptom": "Continental outsole is peeling after three months.",
        "solution": "Stop running in it if the tread is lifting, avoid heat exposure, and start a warranty claim; use shoe adhesive only as a temporary fix for minor separation.",
    },
    "tent-condensation": {
        "answer": (
            "Morning condensation in the REI Half Dome points to ventilation "
            "and moisture management. Open vents when conditions allow, keep "
            "the bag off the tent walls, and store the sleeping bag in a dry bag."
        ),
        "summary": "Condensation can dampen sleeping bags even when the rainfly blocks rain.",
        "symptom": "REI Half Dome tent has condensation every morning and the sleeping bag gets damp.",
        "solution": "Improve ventilation, avoid wall contact, and protect the sleeping bag in a waterproof dry bag.",
    },
    "sleeping-pad-deflated": {
        "answer": (
            "A Therm-a-Rest pad that deflates overnight usually has a pinhole "
            "leak or valve debris. Inflate it, check the valve, find bubbles "
            "with water or soapy water, then patch the marked leak."
        ),
        "summary": "Overnight deflation points to a pinhole leak or valve contamination.",
        "symptom": "Therm-a-Rest sleeping pad deflated overnight.",
        "solution": "Submerge or soap-test the inflated pad, mark the leak, patch it, and rinse debris from the valve.",
    },
    "gel-nimbus-lump": {
        "answer": (
            "A hard lump under the Gel-Nimbus 26 heel can be debris under the "
            "insole, but if the midsole or PureGEL insert itself feels deformed, "
            "treat it as a manufacturing defect and contact ASICS."
        ),
        "summary": "A hard heel lump from day one can indicate a deformed PureGEL insert.",
        "symptom": "ASICS Gel-Nimbus 26 has a hard lump under the heel.",
        "solution": "Remove and reseat the insole; if the midsole remains uneven, stop running in it and request replacement.",
    },
}


def search_sample(
    *,
    preset_id: str | None,
    prompt: str,
    request_id: str,
    session_id: str,
    source_type: SourceType = "sample",
    warning: str | None = None,
) -> AgenticSearchOut:
    preset = SEARCH_PRESETS.get(preset_id or "", _default_search(prompt))
    products = list(preset["products"])
    warnings = _sample_warnings(warning)
    return AgenticSearchOut(
        answer=str(preset["answer"]),
        source_type=source_type,
        trace_source="sample",
        request_id=request_id,
        session_id=session_id,
        warnings=warnings,
        timing=TimingMetadata(total_ms=0),
        summary=str(preset["summary"]),
        product_picks=products,
        related_products=products[1:],
        profile_chips=[
            ProfileChip(label="Intent", value="comparison", kind="session"),
            ProfileChip(label="Channel", value="demo", kind="session"),
        ],
        memory_writes=[
            MemoryWrite(
                label="interest",
                value=products[0].category or "product",
                kind="preference",
                stored=True,
            )
        ],
        tool_timeline=[
            ToolTimelineItem(tool_name="get_user_profile", summary="Loaded demo profile"),
            ToolTimelineItem(tool_name="search_products", summary="Ranked product matches"),
            ToolTimelineItem(tool_name="get_related_products", summary="Found alternatives"),
        ],
        graph_hops=[
            GraphHop(
                source=products[0].name,
                relationship="SIMILAR_TO",
                target=products[-1].name,
                score=0.82,
            )
        ],
        knowledge_chunks=[
            KnowledgeChunk(
                id="sample-search-context",
                text="Demo context combines product attributes, preference signals, and graph relationships.",
                source_type="sample",
                score=0.9,
                features=products[0].signals,
                related_products=[product.name for product in products],
            )
        ],
    )


def diagnosis_sample(
    *,
    preset_id: str | None,
    prompt: str,
    request_id: str,
    session_id: str,
    source_type: SourceType = "sample",
    warning: str | None = None,
) -> IssueDiagnosisOut:
    preset = DIAGNOSIS_PRESETS.get(preset_id or "", _default_diagnosis(prompt))
    symptom = str(preset["symptom"])
    solution = str(preset["solution"])
    warnings = _sample_warnings(warning)
    chunk = KnowledgeChunk(
        id="sample-diagnosis-context",
        text=f"{symptom} Recommended resolution: {solution}",
        source_type="sample",
        score=0.91,
        symptoms=[symptom],
        solutions=[solution],
    )
    return IssueDiagnosisOut(
        answer=str(preset["answer"]),
        source_type=source_type,
        trace_source="sample",
        request_id=request_id,
        session_id=session_id,
        warnings=warnings,
        timing=TimingMetadata(total_ms=0),
        summary=str(preset["summary"]),
        confidence=0.86,
        path=[
            DiagnosisPathStep(label="Symptom", detail=symptom),
            DiagnosisPathStep(label="Likely cause", detail=str(preset["summary"])),
            DiagnosisPathStep(label="Solution", detail=solution),
        ],
        recommended_actions=[
            RecommendedAction(label=solution, priority="high"),
            RecommendedAction(label="Escalate if the issue repeats", priority="medium"),
        ],
        compatible_alternatives=[],
        cited_sources=[
            CitedSource(
                id=chunk.id,
                title="Curated demo support context",
                source_type="sample",
                snippet=chunk.text,
                score=chunk.score,
            )
        ],
        tool_timeline=[
            ToolTimelineItem(tool_name="hybrid_knowledge_search", summary="Matched symptom context"),
            ToolTimelineItem(tool_name="diagnose_product_issue", summary="Mapped symptom to solution"),
        ],
        knowledge_chunks=[chunk],
    )


def _sample_warnings(message: str | None) -> list[DemoWarning]:
    if not message:
        message = "Sample demo data was used."
    return [DemoWarning(code="sample_data_used", message=message)]


def _default_search(prompt: str) -> dict:
    return {
        "answer": f"Sample search response for: {prompt}",
        "summary": "Sample product ranking.",
        "products": [
            ProductCard(
                id="sample-product",
                name="Curated Demo Product",
                brand="Demo",
                category="Retail",
                price=129.0,
                in_stock=True,
                score=0.8,
                rationale="Generic sample product for local development.",
                signals=["sample", "fallback"],
            )
        ],
    }


def _default_diagnosis(prompt: str) -> dict:
    return {
        "answer": f"Sample diagnosis response for: {prompt}",
        "summary": "Sample issue diagnosis.",
        "symptom": prompt,
        "solution": "Run the recommended reset steps and retry.",
    }
