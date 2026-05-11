import {
  ApiError,
  runAgenticSearch,
  runIssueDiagnosis,
  type AgenticSearchOut,
  type DemoWarning,
  type IssueDiagnosisOut,
  type ProductCard,
} from "@/lib/api";
import {
  type CitedSource,
  type DemoMode,
  type DemoProduct,
  type DemoResponse,
  type DemoSource,
  type DiagnosisPathStep,
  type SearchDemoResponse,
  type SupportDemoResponse,
  products,
} from "@/lib/demo-data";

type SubmitDemoRequest = {
  mode: DemoMode;
  prompt: string;
  presetId?: string;
  sessionId: string;
  userId: string;
};

const SEARCH_PRESET_IDS: Record<string, string> = {
  trail_running_shoes: "trail-running-shoes",
  rain_hiking_jacket: "rain-hiking-jacket",
  cold_weather_layers: "cold-weather-layers",
  backpacking_tent_comparison: "backpacking-tent-comparison",
  two_person_backpacking_setup: "two-person-backpacking-setup",
};

const SUPPORT_PRESET_IDS: Record<string, string> = {
  shoes_flat: "running-shoes-feel-flat",
  outsole_peeling: "outsole-peeling",
  tent_condensation: "tent-condensation",
  sleeping_pad_deflated: "sleeping-pad-deflated",
  gel_nimbus_lump: "gel-nimbus-lump",
};

export async function submitDemoRequest({
  mode,
  prompt,
  presetId,
  sessionId,
  userId,
}: SubmitDemoRequest): Promise<DemoResponse> {
  try {
    if (mode === "search") {
      const { data } = await runAgenticSearch({
        prompt,
        session_id: sessionId,
        user_id: userId,
        demo_preset_id: presetId ? SEARCH_PRESET_IDS[presetId] ?? presetId : null,
      });
      return adaptSearchResponse(data, prompt);
    }

    const { data } = await runIssueDiagnosis({
      prompt,
      session_id: sessionId,
      user_id: userId,
      demo_preset_id: presetId ? SUPPORT_PRESET_IDS[presetId] ?? presetId : null,
    });
    return adaptSupportResponse(data, prompt);
  } catch (error) {
    return errorResponse(mode, prompt, sessionId, error);
  }
}

function adaptSearchResponse(data: AgenticSearchOut, prompt: string): SearchDemoResponse {
  const productPicks = data.product_picks ?? [];
  const relatedProducts = data.related_products ?? [];

  return {
    id: data.request_id,
    sessionId: data.session_id,
    source: sourceType(data.source_type),
    query: prompt,
    summary: data.summary || data.answer,
    picks: productPicks.map((product, index) => {
      const productId = registerProduct(product, index);
      return {
        productId,
        product: products[productId],
        why: product.rationale || product.description || "Matched by the live retail agent.",
        signals: product.signals?.length ? product.signals : signalFallback(product),
      };
    }),
    pairedProductIds: relatedProducts.map((product, index) =>
      registerProduct(product, index + productPicks.length),
    ),
    profileWrites: (data.memory_writes ?? []).map((write) => ({
      label: write.label,
      value: write.value,
    })),
    profileChips: (data.profile_chips ?? []).map((chip) =>
      chip.value ? `${chip.label}: ${chip.value}` : chip.label,
    ),
    tools: (data.tool_timeline ?? []).map((tool) => ({
      toolName: tool.tool_name,
      args: tool.label || tool.status || "live tool call",
      result: tool.summary || tool.status || "completed",
      durationMs: tool.duration_ms ?? undefined,
    })),
    graphHops: (data.graph_hops ?? []).map((hop) => ({
      source: hop.source,
      relationship: hop.relationship,
      target: hop.target,
    })),
    chunks: (data.knowledge_chunks ?? []).map((chunk, index) => ({
      title: chunk.title || chunk.id || `Knowledge chunk ${index + 1}`,
      snippet: chunk.text,
      score: chunk.score ?? 0,
    })),
    latencyMs: data.timing?.total_ms ?? data.timing?.upstream_ms ?? 1000,
    tokens: 0,
    warnings: warnings(data.warnings, data.source_type, data.trace_source),
  };
}

function adaptSupportResponse(data: IssueDiagnosisOut, prompt: string): SupportDemoResponse {
  return {
    id: data.request_id,
    sessionId: data.session_id,
    source: sourceType(data.source_type),
    query: prompt,
    summary: data.summary || data.answer,
    confidence: confidenceLabel(data.confidence),
    path: pathSteps(data.path ?? []),
    actions: (data.recommended_actions ?? []).map((action) =>
      action.description ? `${action.label}: ${action.description}` : action.label,
    ),
    sourceRows: (data.cited_sources ?? []).map((source, index) => ({
      kind: sourceKind(source.source_type),
      id: source.id || `source-${index + 1}`,
      title: source.title || "Live source",
      snippet: source.snippet || "Source text was not returned.",
    })),
    alternativeProductIds: (data.compatible_alternatives ?? []).map((product, index) =>
      registerProduct(product, index),
    ),
    tools: (data.tool_timeline ?? []).map((tool) => ({
      toolName: tool.tool_name,
      args: tool.label || tool.status || "live tool call",
      result: tool.summary || tool.status || "completed",
      durationMs: tool.duration_ms ?? undefined,
    })),
    latencyMs: data.timing?.total_ms ?? data.timing?.upstream_ms ?? 1000,
    tokens: 0,
    warnings: warnings(data.warnings, data.source_type, data.trace_source),
  };
}

function registerProduct(product: ProductCard, index: number): string {
  const id = product.id || slug(product.name) || `live-product-${index + 1}`;
  const existing = products[id];
  if (existing) {
    return existing.id;
  }

  products[id] = {
    id,
    name: product.name,
    brand: product.brand || "Agentic Commerce",
    price: product.price ?? 0,
    rating: scoreToRating(product.score),
    reviewCount: 0,
    tag: product.category || product.description || "Live result",
    monogram: monogram(product.name),
    tint: tintFor(id),
  };

  return id;
}

function signalFallback(product: ProductCard): string[] {
  const signals = [product.category, product.brand, product.in_stock === false ? "out of stock" : null]
    .filter((value): value is string => Boolean(value));
  return signals.length ? signals : ["live match"];
}

function pathSteps(
  steps: { label: string; detail?: string | null }[],
): DiagnosisPathStep[] {
  return steps.map((step, index) => ({
    kind: index === 0 ? "symptom" : index === steps.length - 1 ? "solution" : "cause",
    label: step.detail ? `${step.label}: ${step.detail}` : step.label,
  }));
}

function warnings(
  values: DemoWarning[] | undefined,
  source: string,
  traceSource: string | undefined,
): string[] {
  const result = (values ?? []).map((warning) => warning.message);
  if (source !== "live") {
    result.push(`Response source: ${source}.`);
  }
  if (traceSource && traceSource !== "live" && traceSource !== "sample") {
    result.push(`Trace source: ${traceSource}.`);
  }
  return [...new Set(result)];
}

function errorResponse(
  mode: DemoMode,
  prompt: string,
  sessionId: string,
  error: unknown,
): DemoResponse {
  const message = apiErrorMessage(error);
  const base = {
    id: `error-${sessionId}`,
    sessionId,
    source: "inferred" as DemoSource,
    query: prompt,
    summary: message,
    latencyMs: 0,
    tokens: 0,
    warnings: [message],
  };

  if (mode === "search") {
    return {
      ...base,
      picks: [],
      pairedProductIds: [],
      profileWrites: [],
      profileChips: [],
      tools: [],
      graphHops: [],
      chunks: [],
    };
  }

  return {
    ...base,
    confidence: "low",
    path: [],
    actions: [],
    sourceRows: [],
    alternativeProductIds: [],
    tools: [],
  };
}

function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (
      error.body &&
      typeof error.body === "object" &&
      "user_message" in error.body &&
      typeof error.body.user_message === "string"
    ) {
      return error.body.user_message;
    }
    return `Backend request failed with HTTP ${error.status}.`;
  }
  return error instanceof Error ? error.message : "Backend request failed.";
}

function sourceType(value: string): DemoSource {
  if (value === "sample" || value === "fallback" || value === "live") {
    return value;
  }
  return "inferred";
}

function sourceKind(value: string | null | undefined): CitedSource["kind"] {
  const normalized = (value || "").toLowerCase();
  if (normalized.includes("ticket")) {
    return "ticket";
  }
  if (normalized.includes("review")) {
    return "review";
  }
  return "kb";
}

function confidenceLabel(value: number | null | undefined): SupportDemoResponse["confidence"] {
  if (value == null) {
    return "medium";
  }
  if (value >= 0.75) {
    return "high";
  }
  if (value >= 0.45) {
    return "medium";
  }
  return "low";
}

function scoreToRating(score: number | null | undefined): number {
  if (score == null) {
    return 4.3;
  }
  return Math.max(3.5, Math.min(5, Number((3.5 + score * 1.5).toFixed(1))));
}

function slug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 48);
}

function monogram(value: string): string {
  const letters = value.match(/[A-Za-z0-9]+/g) ?? [];
  const first = letters[0]?.[0] ?? "P";
  const second = letters.length > 1 ? letters[1][0] : letters[0]?.[1] ?? "";
  return `${first}${second}`.toUpperCase();
}

function tintFor(id: string): DemoProduct["tint"] {
  const tints = ["#e8eef7", "#efece4", "#ecefe7", "#efeae6", "#e7eaee"];
  const total = id.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return tints[total % tints.length];
}
