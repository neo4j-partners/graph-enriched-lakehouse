from typing import Any, Literal

from pydantic import BaseModel, Field

from .. import __version__


class VersionOut(BaseModel):
    version: str

    @classmethod
    def from_metadata(cls):
        return cls(version=__version__)


DemoMode = Literal["agentic_search", "issue_diagnosis"]
SourceType = Literal["live", "sample", "fallback"]
TraceSource = Literal["live", "sample", "inferred", "unavailable"]


class DemoWarning(BaseModel):
    code: str
    message: str


class TimingMetadata(BaseModel):
    total_ms: int | None = None
    upstream_ms: int | None = None


class DemoError(BaseModel):
    code: str
    user_message: str
    technical_detail: str | None = None
    retryable: bool = False
    fallback_available: bool = False


class DemoRequestBase(BaseModel):
    prompt: str = Field(min_length=1)
    session_id: str | None = None
    user_id: str | None = None
    demo_preset_id: str | None = None
    demo_mode: DemoMode | None = None


class AgenticSearchIn(DemoRequestBase):
    demo_mode: Literal["agentic_search"] | None = "agentic_search"


class IssueDiagnosisIn(DemoRequestBase):
    demo_mode: Literal["issue_diagnosis"] | None = "issue_diagnosis"


class ProductCard(BaseModel):
    id: str | None = None
    name: str
    brand: str | None = None
    category: str | None = None
    description: str | None = None
    price: float | None = None
    in_stock: bool | None = None
    image_url: str | None = None
    score: float | None = None
    rationale: str | None = None
    signals: list[str] = Field(default_factory=list)


class ProfileChip(BaseModel):
    label: str
    value: str
    kind: str | None = None


class MemoryWrite(BaseModel):
    label: str
    value: str
    kind: str | None = None
    stored: bool | None = None


class ToolTimelineItem(BaseModel):
    tool_name: str
    status: str = "completed"
    label: str | None = None
    duration_ms: int | None = None
    summary: str | None = None


class GraphHop(BaseModel):
    source: str
    relationship: str
    target: str
    score: float | None = None


class KnowledgeChunk(BaseModel):
    id: str | None = None
    title: str | None = None
    text: str
    source_type: str | None = None
    score: float | None = None
    features: list[str] = Field(default_factory=list)
    symptoms: list[str] = Field(default_factory=list)
    solutions: list[str] = Field(default_factory=list)
    related_products: list[str] = Field(default_factory=list)


class CitedSource(BaseModel):
    id: str | None = None
    title: str | None = None
    source_type: str | None = None
    snippet: str | None = None
    score: float | None = None


class RecommendedAction(BaseModel):
    label: str
    description: str | None = None
    priority: str | None = None


class DiagnosisPathStep(BaseModel):
    label: str
    detail: str | None = None


class DemoResponseBase(BaseModel):
    mode: DemoMode
    answer: str
    source_type: SourceType
    trace_source: TraceSource = "unavailable"
    request_id: str
    session_id: str
    databricks_request_id: str | None = None
    warnings: list[DemoWarning] = Field(default_factory=list)
    timing: TimingMetadata = Field(default_factory=TimingMetadata)
    raw_endpoint_metadata: dict[str, Any] | None = None


class AgenticSearchOut(DemoResponseBase):
    mode: DemoMode = "agentic_search"
    summary: str | None = None
    product_picks: list[ProductCard] = Field(default_factory=list)
    related_products: list[ProductCard] = Field(default_factory=list)
    profile_chips: list[ProfileChip] = Field(default_factory=list)
    memory_writes: list[MemoryWrite] = Field(default_factory=list)
    tool_timeline: list[ToolTimelineItem] = Field(default_factory=list)
    graph_hops: list[GraphHop] = Field(default_factory=list)
    knowledge_chunks: list[KnowledgeChunk] = Field(default_factory=list)


class IssueDiagnosisOut(DemoResponseBase):
    mode: DemoMode = "issue_diagnosis"
    summary: str | None = None
    confidence: float | None = None
    path: list[DiagnosisPathStep] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    compatible_alternatives: list[ProductCard] = Field(default_factory=list)
    cited_sources: list[CitedSource] = Field(default_factory=list)
    tool_timeline: list[ToolTimelineItem] = Field(default_factory=list)
    knowledge_chunks: list[KnowledgeChunk] = Field(default_factory=list)
