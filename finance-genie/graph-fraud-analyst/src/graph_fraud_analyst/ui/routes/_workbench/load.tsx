// load.tsx
// Screen 2 of the Fraud Analyst workbench. Materializes the selected rings
// into the lakehouse via a 7-step animated pipeline. The backend returns the
// full LoadOut immediately; the choreography (todo → now → done) is run
// client-side on a 700ms timer.

import { useEffect, useRef, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { QueryErrorResetBoundary } from "@tanstack/react-query";
import { ErrorBoundary } from "react-error-boundary";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Circle,
  Database,
  Loader2,
} from "lucide-react";

import { Pill } from "@/components/Pill";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useLoadRings, type LoadOut, type LoadStep } from "@/lib/api";
import { useFlow } from "@/lib/flowContext";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_workbench/load")({
  component: LoadRoute,
});

const STEP_INTERVAL_MS = 700;

function LoadRoute() {
  const navigate = useNavigate();
  const { selectedRings } = useFlow();

  // Empty-state: no rings selected upstream.
  if (selectedRings.length === 0) {
    return (
      <Card className="bg-surface border-line p-8 text-center">
        <div className="mx-auto max-w-md space-y-3">
          <h2 className="text-lg font-semibold text-ink">Pick rings first</h2>
          <p className="text-sm text-ink-2">
            Head back to Search and select one or more fraud rings before
            loading them into the lakehouse.
          </p>
          <Button
            variant="default"
            onClick={() => navigate({ to: "/search" })}
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Search
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <QueryErrorResetBoundary>
      {({ reset }) => (
        <ErrorBoundary
          onReset={reset}
          fallbackRender={({ error, resetErrorBoundary }) => (
            <LoadErrorCard
              message={error instanceof Error ? error.message : "Load failed"}
              onRetry={resetErrorBoundary}
              onBack={() => navigate({ to: "/search" })}
            />
          )}
        >
          <LoadBody selectedRings={selectedRings} />
        </ErrorBoundary>
      )}
    </QueryErrorResetBoundary>
  );
}

function LoadBody({ selectedRings }: { selectedRings: string[] }) {
  const navigate = useNavigate();
  const [loadOut, setLoadOut] = useState<LoadOut | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const fetchedRef = useRef(false);

  const mutation = useLoadRings({
    mutation: {
      onSuccess: (res) => setLoadOut(res.data),
    },
  });

  // Fire the load mutation exactly once.
  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    mutation.mutate({ ring_ids: selectedRings });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRings]);

  // Walk the step cursor on a 700ms timer once data lands.
  useEffect(() => {
    if (!loadOut) return;
    if (currentStepIndex >= loadOut.steps.length) return;

    const timer = setInterval(() => {
      setCurrentStepIndex((idx) => {
        if (idx >= loadOut.steps.length) return idx;
        return idx + 1;
      });
    }, STEP_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [loadOut, currentStepIndex]);

  // Surface backend errors through the ErrorBoundary so the user sees the
  // retry-able card instead of a stuck "loading" view.
  if (mutation.isError) {
    throw mutation.error;
  }

  const stepsComplete =
    loadOut !== null && currentStepIndex >= loadOut.steps.length;
  const ringWord = selectedRings.length === 1 ? "ring" : "rings";

  return (
    <div className="p-6 space-y-4">
      {/* Header strip */}
      <header className="flex flex-wrap items-center gap-3">
        <Database className="h-4 w-4 text-ink-2" />
        <h1 className="text-sm font-medium text-ink-2">
          Loading {selectedRings.length} {ringWord} → Lakehouse
        </h1>
        <div className="flex flex-wrap gap-1">
          {selectedRings.map((ringId) => (
            <Pill key={ringId} intent="mono">
              {ringId}
            </Pill>
          ))}
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Pipeline progress (left, spans 2) */}
        <Card className="lg:col-span-2 p-4 bg-surface border-line">
          <div className="mb-3">
            <div className="text-sm font-medium text-ink">Pipeline progress</div>
            <div className="text-xs text-muted-ink">
              Streaming the selected subgraph into Delta tables.
            </div>
          </div>

          {loadOut === null ? (
            <PipelineSkeleton />
          ) : (
            <PipelineSteps
              steps={loadOut.steps}
              currentStepIndex={currentStepIndex}
            />
          )}
        </Card>

        {/* Right column */}
        <div className="space-y-4">
          {/* Target tables */}
          <Card className="p-4 bg-surface border-line">
            <div className="mb-3">
              <div className="text-sm font-medium text-ink">Target tables</div>
              <div className="text-xs text-muted-ink">
                Destination Delta tables in fraud_signals.
              </div>
            </div>
            {loadOut === null ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-6 w-full" />
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-start gap-1.5">
                {loadOut.target_tables.map((t) => (
                  <Pill key={t} intent="mono">
                    {t}
                  </Pill>
                ))}
              </div>
            )}
          </Card>

          {/* Row counts */}
          <Card className="p-4 bg-surface border-line">
            <div className="mb-3">
              <div className="text-sm font-medium text-ink">Row counts</div>
              <div className="text-xs text-muted-ink">
                Live counts after ingestion.
              </div>
            </div>
            {loadOut === null ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-5 w-full" />
                ))}
              </div>
            ) : (
              <dl className="space-y-1.5">
                {Object.entries(loadOut.row_counts).map(([table, count]) => (
                  <div
                    key={table}
                    className="flex items-center justify-between gap-3"
                  >
                    <dt className="font-mono text-xs text-ink-2 truncate">
                      {table}
                    </dt>
                    <dd className="font-mono tabular-nums text-sm text-ink">
                      {count.toLocaleString()}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </Card>

          {/* Quality checks */}
          <Card className="p-4 bg-surface border-line">
            <div className="mb-3">
              <div className="text-sm font-medium text-ink">Quality checks</div>
              <div className="text-xs text-muted-ink">
                Validations from the gold-tables pipeline.
              </div>
            </div>
            {loadOut === null ? (
              <div className="space-y-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-7 w-full" />
                ))}
              </div>
            ) : (
              <ul>
                {loadOut.quality_checks.map((q, i) => (
                  <li
                    key={q.name}
                    className={cn(
                      "flex items-center justify-between py-2 text-sm",
                      i < loadOut.quality_checks.length - 1 &&
                        "border-b border-line",
                    )}
                  >
                    <span className="text-ink-2 pr-2">{q.name}</span>
                    {q.passed ? (
                      <CheckCircle2
                        className="h-4 w-4 text-good shrink-0"
                        aria-label="Passed"
                      />
                    ) : (
                      <AlertCircle
                        className="h-4 w-4 text-risk-high shrink-0"
                        aria-label="Failed"
                      />
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-6 flex items-center justify-between">
        <Button
          variant="outline"
          onClick={() => navigate({ to: "/search" })}
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Search
        </Button>
        <Button
          disabled={!stepsComplete}
          onClick={() => navigate({ to: "/analyze" })}
        >
          Continue to Analyze
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function LoadErrorCard({
  message,
  onRetry,
  onBack,
}: {
  message: string;
  onRetry: () => void;
  onBack: () => void;
}) {
  return (
    <Card className="p-4 flex items-start justify-between gap-4 border-risk-high/40">
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-risk-high mt-0.5" />
        <div>
          <div className="text-sm font-medium text-ink">Load failed</div>
          <div className="text-xs text-muted-ink mt-1">{message}</div>
        </div>
      </div>
      <div className="flex gap-2">
        <Button variant="outline" onClick={onBack}>
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
        <Button variant="outline" onClick={onRetry}>
          Retry
        </Button>
      </div>
    </Card>
  );
}

// ─── Sub-components ────────────────────────────────────────────────────

function PipelineSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 7 }).map((_, i) => (
        <div key={i} className="flex items-start gap-3">
          <Skeleton className="h-6 w-6 rounded-full" />
          <Skeleton className="h-5 flex-1" />
        </div>
      ))}
    </div>
  );
}

function PipelineSteps({
  steps,
  currentStepIndex,
}: {
  steps: LoadStep[];
  currentStepIndex: number;
}) {
  return (
    <ol className="relative">
      {/* Vertical guide line behind the icon column */}
      <div
        className="absolute left-3 top-3 bottom-3 border-l border-line"
        aria-hidden
      />
      {steps.map((step, i) => {
        const status: LoadStep["status"] =
          i < currentStepIndex
            ? "done"
            : i === currentStepIndex
              ? "now"
              : "todo";
        return (
          <li
            key={step.label}
            className="relative flex items-start gap-3 py-3"
          >
            <StepIcon status={status} />
            <div className="flex-1 min-w-0">
              <div
                className={cn(
                  "text-sm",
                  status === "done" && "text-ink line-through opacity-80",
                  status === "now" && "text-ink font-medium",
                  status === "todo" && "text-muted-ink",
                )}
              >
                {step.label}
              </div>
              {status === "now" && (
                <div className="mt-1 h-0.5 w-24 bg-accent-ink animate-pulse rounded-sm" />
              )}
              {step.detail && status !== "todo" && (
                <div className="text-xs text-muted-ink mt-0.5">
                  {step.detail}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function StepIcon({ status }: { status: LoadStep["status"] }) {
  if (status === "done") {
    return (
      <div className="relative z-10 flex h-6 w-6 items-center justify-center rounded-full bg-good text-canvas shrink-0">
        <Check className="h-3.5 w-3.5" strokeWidth={3} />
      </div>
    );
  }
  if (status === "now") {
    return (
      <div className="relative z-10 flex h-6 w-6 items-center justify-center rounded-full bg-canvas border border-accent-ink shrink-0">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-accent-ink" />
      </div>
    );
  }
  return (
    <div className="relative z-10 flex h-6 w-6 items-center justify-center rounded-full bg-canvas shrink-0">
      <Circle className="h-3.5 w-3.5 text-muted-ink" />
    </div>
  );
}
