// search.tsx
// Screen 1 of the Fraud Analyst workbench. Search the Neo4j-backed FastAPI
// service for fraud rings, risky accounts, or central hub accounts. The route
// lives inside the `_workbench` pathless layout, so the URL is `/search` and
// Shell is provided by the parent.

import { Suspense, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { QueryErrorResetBoundary } from "@tanstack/react-query";
import { ErrorBoundary } from "react-error-boundary";
import {
  AlertTriangle,
  ArrowRight,
  Network,
  Search as SearchIcon,
} from "lucide-react";

import { Pill, type PillIntent } from "@/components/Pill";
import { RiskBar } from "@/components/RiskBar";
import { RingThumb } from "@/components/RingThumb";
import { NetworkPreview } from "@/components/NetworkPreview";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useSearchCentralAccountsSuspense,
  useSearchRingsSuspense,
  useSearchRiskAccountsSuspense,
  type HubAccountOut,
  type RingOut,
  type RiskAccountOut,
} from "@/lib/api";
import { useFlow } from "@/lib/flowContext";
import { RISK_LABEL, RISK_PILL_INTENT } from "@/lib/riskColors";
import selector from "@/lib/selector";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_workbench/search")({
  component: SearchScreen,
});

// UI-only mode discriminator. Each mode maps to a different Suspense hook.
type Mode = "fraud_rings" | "risk_scores" | "central_accounts";

interface ChoiceMeta {
  id: Mode;
  title: string;
  blurb: string;
  Icon: typeof SearchIcon;
}

const CHOICES: ChoiceMeta[] = [
  {
    id: "fraud_rings",
    title: "Fraud rings",
    blurb: "Communities of accounts moving money in tight loops.",
    Icon: SearchIcon,
  },
  {
    id: "risk_scores",
    title: "Risk scores",
    blurb: "Top accounts by individual risk score.",
    Icon: AlertTriangle,
  },
  {
    id: "central_accounts",
    title: "Central accounts",
    blurb: "Accounts that bridge the most paths.",
    Icon: Network,
  },
];

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function bandPillIntent(band: "Low" | "Medium" | "High"): PillIntent {
  if (band === "High") return "risk-high";
  if (band === "Medium") return "risk-med";
  return "default";
}

function SearchScreen() {
  const navigate = useNavigate();
  const { selectedRings, toggleRing, clearRings } = useFlow();

  const [mode, setMode] = useState<Mode>("fraud_rings");
  const [dateRange, setDateRange] = useState("Last 30 days");
  const [minAmount, setMinAmount] = useState<number>(500);
  const [maxNodes, setMaxNodes] = useState<number>(500);

  const handleModeChange = (next: Mode) => {
    if (next === mode) return;
    setMode(next);
    if (next !== "fraud_rings") clearRings();
  };

  const continueDisabled =
    mode === "fraud_rings" && selectedRings.length === 0;

  // Note: dateRange and minAmount are kept in the UI for fidelity but the
  // backend does not yet honor them; only maxNodes is part of the query key,
  // so changing it auto-refetches via React Query. The "Search Neo4j" button
  // is a visual affordance — refetch already happens implicitly via maxNodes.
  return (
    <div className="p-6 space-y-4">
      <header>
        <h1 className="text-xl font-semibold text-ink">Surface fraud signals</h1>
        <p className="text-sm text-muted-ink">
          Search the Neo4j relationship graph for suspicious structural patterns.
        </p>
      </header>

      {/* Mode card */}
      <Card className="p-4">
        <div className="mb-3">
          <div className="text-sm font-medium text-ink-2">
            What are you looking for?
          </div>
          <div className="text-xs text-muted-ink">Pick one pattern type.</div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {CHOICES.map((c) => {
            const selected = c.id === mode;
            const Icon = c.Icon;
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => handleModeChange(c.id)}
                aria-pressed={selected}
                className={cn(
                  "flex flex-col items-start text-left p-4 rounded-md border-2 transition-colors",
                  selected
                    ? "border-accent-ink bg-accent-soft text-ink"
                    : "border-line-2 bg-surface text-ink-2 hover:border-line-3",
                )}
              >
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4" />
                  <span className="text-sm font-medium">{c.title}</span>
                </div>
                <span className="text-xs text-muted-ink mt-2">{c.blurb}</span>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Filters strip */}
      <Card>
        <div className="flex flex-wrap gap-3 items-end p-4">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase tracking-wide text-muted-ink">
              Date range
            </label>
            <Select value={dateRange} onValueChange={setDateRange}>
              <SelectTrigger className="w-[170px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Last 7 days">Last 7 days</SelectItem>
                <SelectItem value="Last 30 days">Last 30 days</SelectItem>
                <SelectItem value="Last 90 days">Last 90 days</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase tracking-wide text-muted-ink">
              Minimum amount
            </label>
            <div className="relative">
              <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-ink">
                $
              </span>
              <Input
                type="number"
                inputMode="numeric"
                min={0}
                value={minAmount}
                onChange={(e) => setMinAmount(Number(e.target.value))}
                className="pl-6 w-[140px] font-mono tabular-nums"
              />
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase tracking-wide text-muted-ink">
              Max nodes
            </label>
            <Input
              type="number"
              inputMode="numeric"
              min={1}
              value={maxNodes}
              onChange={(e) => setMaxNodes(Number(e.target.value))}
              className="w-[120px] font-mono tabular-nums"
            />
          </div>

          <div className="ml-auto">
            <Button type="button">
              <SearchIcon className="h-4 w-4" />
              Search Neo4j
            </Button>
          </div>
        </div>
      </Card>

      {/* Results region: ErrorBoundary wraps Suspense, which wraps the
          mode-specific data-fetching subtree. Switching modes remounts the
          inner ResultsBody so only the active mode's hook fires. */}
      <QueryErrorResetBoundary>
        {({ reset }) => (
          <ErrorBoundary
            onReset={reset}
            fallbackRender={({ error, resetErrorBoundary }) => (
              <ErrorCard
                message={error instanceof Error ? error.message : "Search failed"}
                onRetry={resetErrorBoundary}
              />
            )}
          >
            <Suspense fallback={<ResultsSkeleton />}>
              <ResultsBody
                mode={mode}
                maxNodes={maxNodes}
                selectedRings={selectedRings}
                onToggleRing={toggleRing}
              />
            </Suspense>
          </ErrorBoundary>
        )}
      </QueryErrorResetBoundary>

      {/* Continue footer */}
      <div className="mt-6 flex items-center justify-between">
        <span className="text-xs text-muted-ink">
          {mode === "fraud_rings" && selectedRings.length > 0
            ? `${selectedRings.length} ring${selectedRings.length === 1 ? "" : "s"} selected`
            : ""}
        </span>
        <Button
          type="button"
          disabled={continueDisabled}
          onClick={() => navigate({ to: "/load" })}
        >
          Continue to Load
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// ─── Sub-components ──────────────────────────────────────────────────────

interface ResultsBodyProps {
  mode: Mode;
  maxNodes: number;
  selectedRings: string[];
  onToggleRing: (ringId: string) => void;
}

function ResultsBody({
  mode,
  maxNodes,
  selectedRings,
  onToggleRing,
}: ResultsBodyProps) {
  if (mode === "fraud_rings") {
    return (
      <RingsBody
        maxNodes={maxNodes}
        selectedRings={selectedRings}
        onToggleRing={onToggleRing}
      />
    );
  }
  if (mode === "risk_scores") {
    return <RiskBody />;
  }
  return <HubBody />;
}

function RingsBody({
  maxNodes,
  selectedRings,
  onToggleRing,
}: {
  maxNodes: number;
  selectedRings: string[];
  onToggleRing: (ringId: string) => void;
}) {
  const { data: rings } = useSearchRingsSuspense({
    params: { max_nodes: maxNodes },
    ...selector<RingOut[]>(),
  });
  return (
    <RingResults
      rings={rings}
      selectedRings={selectedRings}
      onToggle={onToggleRing}
    />
  );
}

function RiskBody() {
  const { data: rows } = useSearchRiskAccountsSuspense(
    selector<RiskAccountOut[]>(),
  );
  return <RiskResults rows={rows} />;
}

function HubBody() {
  const { data: rows } = useSearchCentralAccountsSuspense(
    selector<HubAccountOut[]>(),
  );
  return <HubResults rows={rows} />;
}

function ResultsSkeleton() {
  return (
    <Card className="p-4 space-y-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </Card>
  );
}

function ErrorCard({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <Card className="p-4 flex items-start justify-between gap-4 border-risk-high/40">
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-risk-high mt-0.5" />
        <div>
          <div className="text-sm font-medium text-ink">Search failed</div>
          <div className="text-xs text-muted-ink mt-1">{message}</div>
        </div>
      </div>
      <Button variant="outline" onClick={onRetry}>
        Retry
      </Button>
    </Card>
  );
}

function EmptyRingsCard() {
  return (
    <Card className="p-8 flex flex-col items-center text-center">
      <svg viewBox="0 0 220 80" width={220} height={80} aria-hidden="true">
        <g stroke="currentColor" strokeWidth={1} fill="none" className="text-line-3">
          <circle cx={40} cy={40} r={6} />
          <circle cx={90} cy={20} r={4} />
          <circle cx={105} cy={55} r={5} />
          <circle cx={155} cy={30} r={4} />
          <circle cx={180} cy={60} r={6} />
          <line x1={40} y1={40} x2={90} y2={20} />
          <line x1={40} y1={40} x2={105} y2={55} />
          <line x1={90} y1={20} x2={155} y2={30} />
          <line x1={105} y1={55} x2={180} y2={60} />
          <line x1={155} y1={30} x2={180} y2={60} />
        </g>
      </svg>
      <p className="mt-3 text-sm text-muted-ink">
        Run a search to see suspicious patterns from the graph.
      </p>
    </Card>
  );
}

function RingResults({
  rings,
  selectedRings,
  onToggle,
}: {
  rings: RingOut[];
  selectedRings: string[];
  onToggle: (ringId: string) => void;
}) {
  if (rings.length === 0) return <EmptyRingsCard />;

  return (
    <div className="space-y-3">
      <NetworkPreview
        rings={rings.map((r) => ({
          ring_id: r.ring_id,
          nodes: r.nodes,
          topology: r.topology,
          risk: r.risk,
          graph: r.graph,
        }))}
        selectedRingIds={selectedRings}
        onToggle={onToggle}
        defaultOpen
      />

      <Card className="overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10" />
              <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink">
                Ring
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink">
                Topology
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink text-right">
                Nodes
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink text-right">
                Volume
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink">
                Shared identifiers
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink">
                Risk
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rings.map((r) => {
              const selected = selectedRings.includes(r.ring_id);
              return (
                <TableRow
                  key={r.ring_id}
                  className={cn(
                    "border-b border-line",
                    selected && "bg-accent-soft/40",
                  )}
                >
                  <TableCell>
                    <Checkbox
                      checked={selected}
                      onCheckedChange={() => onToggle(r.ring_id)}
                      aria-label={`Select ${r.ring_id}`}
                    />
                  </TableCell>
                  <TableCell>
                    <Pill intent="mono">{r.ring_id}</Pill>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col items-start">
                      <RingThumb
                        ring={{
                          ring_id: r.ring_id,
                          nodes: r.nodes,
                          topology: r.topology,
                          risk: r.risk,
                          graph: r.graph,
                        }}
                        width={140}
                        height={80}
                        selected={selected}
                      />
                      <span className="text-[11px] text-muted-ink mt-1">
                        {r.topology}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums">
                    {r.nodes}
                  </TableCell>
                  <TableCell className="text-right font-mono tabular-nums">
                    {currency.format(r.volume)}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {r.shared_identifiers.map((id) => (
                        <Pill key={id}>{id}</Pill>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <RiskBar score={r.risk_score} risk={r.risk} />
                      <Pill intent={RISK_PILL_INTENT[r.risk]}>
                        {RISK_LABEL[r.risk]}
                      </Pill>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}

function RiskResults({ rows }: { rows: RiskAccountOut[] }) {
  return (
    <Card className="overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink">
              Account
            </TableHead>
            <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink">
              Risk
            </TableHead>
            <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink">
              Velocity
            </TableHead>
            <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink">
              Merchant diversity
            </TableHead>
            <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink text-right">
              Account age
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.account_id} className="border-b border-line">
              <TableCell>
                <Pill intent="mono">{r.account_id}</Pill>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <RiskBar score={r.risk_score} />
                  <span className="font-mono tabular-nums text-xs text-ink-2">
                    {r.risk_score.toFixed(2)}
                  </span>
                </div>
              </TableCell>
              <TableCell>
                <Pill intent={bandPillIntent(r.velocity)}>{r.velocity}</Pill>
              </TableCell>
              <TableCell>
                <Pill intent={bandPillIntent(r.merchant_diversity)}>
                  {r.merchant_diversity}
                </Pill>
              </TableCell>
              <TableCell className="text-right font-mono tabular-nums">
                {r.account_age_days}d
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function HubResults({ rows }: { rows: HubAccountOut[] }) {
  return (
    <Card className="overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink">
              Account
            </TableHead>
            <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink text-right">
              Neighbors
            </TableHead>
            <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink">
              Betweenness
            </TableHead>
            <TableHead className="text-[11px] uppercase tracking-wide text-muted-ink text-right">
              Shortest paths
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.account_id} className="border-b border-line">
              <TableCell>
                <Pill intent="mono">{r.account_id}</Pill>
              </TableCell>
              <TableCell className="text-right font-mono tabular-nums">
                {r.neighbors}
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <BetweennessBar score={r.betweenness} />
                  <span className="font-mono tabular-nums text-xs text-ink-2">
                    {r.betweenness.toFixed(2)}
                  </span>
                </div>
              </TableCell>
              <TableCell className="text-right font-mono tabular-nums">
                {r.shortest_paths}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function BetweennessBar({ score, width = 120 }: { score: number; width?: number }) {
  const clamped = Math.max(0, Math.min(1, score));
  return (
    <div
      className="h-1.5 rounded-sm bg-canvas-soft border border-line overflow-hidden"
      style={{ width: `${width}px` }}
    >
      <div
        className="h-full rounded-sm bg-ink-2"
        style={{ width: `${clamped * 100}%` }}
      />
    </div>
  );
}
