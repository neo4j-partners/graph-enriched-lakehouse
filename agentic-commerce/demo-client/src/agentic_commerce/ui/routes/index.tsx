import { type FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  Activity,
  ArrowRight,
  Brain,
  Check,
  CircleHelp,
  Clock,
  PackagePlus,
  RefreshCcw,
  Search,
  Send,
  Sparkles,
  Star,
  Wrench,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { submitDemoRequest } from "@/lib/demo-client";
import {
  type DemoProfile,
  type DemoProfilePrompt,
  type DemoMode,
  type DemoProduct,
  type DemoResponse,
  type RecentMemoryActivity,
  type SearchDemoResponse,
  type SupportDemoResponse,
  demoProfiles,
  products,
  searchSamples,
  supportSamples,
} from "@/lib/demo-data";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  component: () => <DemoClient />,
});

const searchPresetLabels: Record<string, string> = {
  trail_running_shoes: "waterproof trail shoes under $150",
  rain_hiking_jacket: "packable rain shell for day hikes",
  cold_weather_layers: "cold-weather running layers",
  backpacking_tent_comparison: "compare 2-person backpacking tents",
  two_person_backpacking_setup: "2-person backpacking setup under $750",
};

const supportPresetLabels: Record<string, string> = {
  shoes_flat: "running shoes feel flat",
  outsole_peeling: "outsole peeling after 3 months",
  tent_condensation: "tent condensation dampens bag",
  sleeping_pad_deflated: "sleeping pad deflated overnight",
  gel_nimbus_lump: "hard heel lump in Gel-Nimbus",
};

const MEMORY_TOOL_NAMES = new Set([
  "get_user_profile",
  "track_preference",
  "recommend_for_user",
  "remember_message",
  "recall_memory",
  "search_memory",
]);

function newSessionId() {
  if (window.crypto?.randomUUID) {
    return `demo-${window.crypto.randomUUID().slice(0, 8)}`;
  }
  return `demo-${Date.now().toString(36)}`;
}

function activityId(prefix: string) {
  if (window.crypto?.randomUUID) {
    return `${prefix}-${window.crypto.randomUUID().slice(0, 8)}`;
  }
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function randomDemoProfile() {
  return demoProfiles[Math.floor(Math.random() * demoProfiles.length)] ?? demoProfiles[0];
}

function nextDemoProfile(current: DemoProfile) {
  if (demoProfiles.length < 2) {
    return current;
  }
  let next = randomDemoProfile();
  while (next.id === current.id) {
    next = randomDemoProfile();
  }
  return next;
}

function isSearchResponse(response: DemoResponse | null): response is SearchDemoResponse {
  return Boolean(response && "picks" in response);
}

function isSupportResponse(response: DemoResponse | null): response is SupportDemoResponse {
  return Boolean(response && "path" in response);
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatDuration(value: number | undefined) {
  return typeof value === "number" && value > 0 ? `${value}ms` : "n/a";
}

function formatActivityTime(timestamp: number) {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(timestamp);
}

function unique(values: string[]) {
  return [...new Set(values.filter(Boolean))];
}

function activityFromResponse(response: DemoResponse, prompt: string): RecentMemoryActivity[] {
  const timestamp = Date.now();
  const activities: RecentMemoryActivity[] = [
    {
      id: activityId("prompt"),
      kind: "prompt",
      label: response.source === "live" ? "Live prompt" : "Prompt",
      value: prompt,
      detail: `session ${response.sessionId ?? "local"} / ${response.source}`,
      timestamp,
    },
  ];

  const relevantTools = response.tools.filter((tool) => MEMORY_TOOL_NAMES.has(tool.toolName));
  for (const tool of relevantTools) {
    activities.push({
      id: activityId("tool"),
      kind: "tool",
      label: tool.toolName,
      value: tool.result,
      detail: tool.args,
      timestamp,
    });
  }

  if (isSearchResponse(response)) {
    if (response.profileChips.length) {
      activities.push({
        id: activityId("profile-read"),
        kind: "profile_read",
        label: "Profile read",
        value: response.profileChips.join(", "),
        detail: "get_user_profile returned live profile chips",
        timestamp,
      });
    }
    for (const write of response.profileWrites) {
      activities.push({
        id: activityId("memory-write"),
        kind: "memory_write",
        label: write.label,
        value: write.value,
        detail: "track_preference write",
        timestamp,
      });
    }
  }

  return activities;
}

function ProductImage({ product, className }: { product: DemoProduct; className?: string }) {
  return (
    <div
      className={cn(
        "relative grid place-items-center overflow-hidden rounded-md font-mono text-xl font-semibold text-neutral-700",
        "after:absolute after:inset-0 after:bg-[repeating-linear-gradient(45deg,rgba(20,19,15,0.05)_0_1px,transparent_1px_8px)]",
        className,
      )}
      style={{ background: product.tint }}
      aria-hidden="true"
    >
      <span className="relative z-10">{product.monogram}</span>
    </div>
  );
}

function ProductCardView({
  product,
  rank,
  rationale,
  signals,
}: {
  product: DemoProduct;
  rank?: number;
  rationale?: string;
  signals?: string[];
}) {
  return (
    <Card className="relative overflow-visible rounded-lg border-[#ded8c9] bg-white shadow-sm">
      {rank ? (
        <div className="absolute -left-2 -top-2 grid size-7 place-items-center rounded-full bg-neutral-950 font-mono text-xs text-white">
          {rank}
        </div>
      ) : null}
      <CardContent className="grid gap-4 p-4 sm:grid-cols-[7.5rem_1fr_auto] sm:items-center">
        <ProductImage product={product} className="h-28 sm:h-24" />
        <div className="min-w-0 space-y-2">
          <div className="font-mono text-[11px] uppercase tracking-wide text-neutral-500">
            {product.brand} / {product.tag}
          </div>
          <div className="text-base font-semibold text-neutral-950">{product.name}</div>
          <p className="max-w-2xl text-sm leading-6 text-neutral-700">{rationale}</p>
          {signals?.length ? (
            <div className="flex flex-wrap gap-1.5">
              {signals.map((signal, index) => (
                <span
                  key={`${signal}-${index}`}
                  className="rounded border border-blue-100 bg-blue-50 px-2 py-1 font-mono text-[11px] text-blue-800"
                >
                  {signal}
                </span>
              ))}
            </div>
          ) : null}
        </div>
        <div className="flex items-center justify-between gap-3 sm:flex-col sm:items-end">
          <div className="text-right">
            <div className="font-mono text-lg font-semibold text-neutral-950">
              ${product.price}
            </div>
            <div className="flex items-center gap-1 font-mono text-[11px] text-neutral-500">
              <Star className="size-3 fill-amber-400 text-amber-400" />
              {product.rating} / {formatNumber(product.reviewCount)}
            </div>
          </div>
          <Button size="sm" variant="outline" className="border-[#ded8c9]">
            <PackagePlus className="size-4" />
            Add
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function SmallProductCard({ product }: { product: DemoProduct }) {
  return (
    <Card className="rounded-md border-[#ded8c9] bg-white shadow-sm transition-colors hover:border-neutral-900">
      <CardContent className="space-y-2 p-3">
        <ProductImage product={product} className="h-16 text-base" />
        <div>
          <div className="font-mono text-[10px] uppercase tracking-wide text-neutral-500">
            {product.brand}
          </div>
          <div className="line-clamp-2 min-h-9 text-sm font-medium text-neutral-950">
            {product.name}
          </div>
        </div>
        <div className="font-mono text-xs text-neutral-700">${product.price}</div>
      </CardContent>
    </Card>
  );
}

function WarningList({ warnings }: { warnings?: string[] }) {
  if (!warnings?.length) {
    return null;
  }

  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
      {warnings.map((warning, index) => (
        <div key={`${warning}-${index}`}>{warning}</div>
      ))}
    </div>
  );
}

function Header({
  mode,
  setMode,
  activeProfile,
  profileChips,
  recentActivity,
  busy,
  reset,
  switchProfile,
  submitProfilePrompt,
}: {
  mode: DemoMode;
  setMode: (mode: DemoMode) => void;
  activeProfile: DemoProfile;
  profileChips: string[];
  recentActivity: RecentMemoryActivity[];
  busy: boolean;
  reset: () => void;
  switchProfile: () => void;
  submitProfilePrompt: (prompt: DemoProfilePrompt) => void;
}) {
  const displayChips = unique([...activeProfile.chips, ...profileChips]).slice(0, 5);

  return (
    <header className="sticky top-0 z-20 border-b border-[#ded8c9] bg-[#faf8f3]/95 px-4 py-3 backdrop-blur md:px-7">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 font-mono text-sm text-neutral-950">
          <span className="grid size-5 place-items-center rounded bg-neutral-950">
            <span className="size-2 rounded-[2px] bg-[#faf8f3]" />
          </span>
          <span>retail</span>
          <span className="text-neutral-400">/</span>
          <span>agent</span>
        </div>

        <div className="flex rounded-lg bg-neutral-950/5 p-1">
          <Button
            type="button"
            size="sm"
            variant={mode === "search" ? "secondary" : "ghost"}
            className={cn(
              "h-8 rounded-md px-3 text-xs",
              mode === "search" ? "bg-white text-neutral-950 shadow-sm" : "text-neutral-600",
            )}
            onClick={() => setMode("search")}
          >
            <Search className="size-3.5" />
            <span className="font-mono text-[10px] text-neutral-400">01</span>
            Agentic search
          </Button>
          <Button
            type="button"
            size="sm"
            variant={mode === "support" ? "secondary" : "ghost"}
            className={cn(
              "h-8 rounded-md px-3 text-xs",
              mode === "support" ? "bg-white text-neutral-950 shadow-sm" : "text-neutral-600",
            )}
            onClick={() => setMode("support")}
          >
            <Wrench className="size-3.5" />
            <span className="font-mono text-[10px] text-neutral-400">02</span>
            Issue diagnosis
          </Button>
        </div>

        <div className="min-w-0 flex-1" />

        <Sheet>
          <SheetTrigger asChild>
            <Button
              type="button"
              variant="outline"
              className="h-auto max-w-full justify-start gap-2 rounded-full border-[#ded8c9] bg-white px-2.5 py-1.5 text-xs text-neutral-700 hover:bg-white"
            >
              <span className="grid size-6 shrink-0 place-items-center rounded-full bg-neutral-950 font-mono text-[10px] text-white">
                {activeProfile.initials}
              </span>
              <span className="min-w-0 text-left">
                <span className="block truncate font-medium text-neutral-950">
                  {activeProfile.label}
                </span>
                <span className="flex min-w-0 flex-wrap gap-1">
                  {displayChips.slice(0, 3).map((chip) => (
                    <span
                      key={chip}
                      className="rounded bg-blue-50 px-1.5 py-0.5 font-mono text-[10px] text-blue-800"
                    >
                      {chip}
                    </span>
                  ))}
                </span>
              </span>
            </Button>
          </SheetTrigger>
          <ProfileSheet
            activeProfile={activeProfile}
            profileChips={profileChips}
            recentActivity={recentActivity}
            busy={busy}
            reset={reset}
            switchProfile={switchProfile}
            submitProfilePrompt={submitProfilePrompt}
          />
        </Sheet>

        <Button
          type="button"
          size="sm"
          variant="outline"
          className="border-[#ded8c9] bg-white text-xs"
          onClick={reset}
        >
          <RefreshCcw className="size-3.5" />
          Reset session
        </Button>
      </div>
    </header>
  );
}

function ProfileSheet({
  activeProfile,
  profileChips,
  recentActivity,
  busy,
  reset,
  switchProfile,
  submitProfilePrompt,
}: {
  activeProfile: DemoProfile;
  profileChips: string[];
  recentActivity: RecentMemoryActivity[];
  busy: boolean;
  reset: () => void;
  switchProfile: () => void;
  submitProfilePrompt: (prompt: DemoProfilePrompt) => void;
}) {
  const displayChips = unique([...activeProfile.chips, ...profileChips]);

  return (
    <SheetContent className="flex h-full w-full flex-col overflow-y-auto border-[#ded8c9] bg-[#faf8f3] p-0 sm:max-w-lg">
      <SheetHeader className="border-b border-[#ded8c9] px-5 py-5 text-left">
        <div className="flex items-start gap-3 pr-8">
          <span className="grid size-11 shrink-0 place-items-center rounded-full bg-neutral-950 font-mono text-sm text-white">
            {activeProfile.initials}
          </span>
          <div className="min-w-0">
            <SheetTitle className="text-lg text-neutral-950">{activeProfile.name}</SheetTitle>
            <SheetDescription className="mt-1 text-sm leading-6 text-neutral-600">
              {activeProfile.persona}
            </SheetDescription>
            <div className="mt-2 font-mono text-[10px] text-neutral-500">
              user_id / {activeProfile.id}
            </div>
          </div>
        </div>
      </SheetHeader>

      <div className="flex-1 divide-y divide-[#ded8c9]">
        <section className="space-y-3 px-5 py-4">
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-neutral-500">
            Profile chips
          </div>
          <div className="flex flex-wrap gap-1.5">
            {displayChips.map((chip) => (
              <span
                key={chip}
                className="rounded border border-blue-100 bg-blue-50 px-2 py-1 font-mono text-[11px] text-blue-800"
              >
                {chip}
              </span>
            ))}
          </div>
          {profileChips.length ? (
            <p className="text-xs leading-5 text-neutral-500">
              Live chips were returned by the agent profile trace for this demo user.
            </p>
          ) : (
            <p className="text-xs leading-5 text-neutral-500">
              Seeded demo traits are shown now. Live profile chips appear here after the
              agent calls profile tools.
            </p>
          )}
        </section>

        <section className="space-y-3 px-5 py-4">
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-neutral-500">
            Seeded preferences
          </div>
          <div className="grid gap-2">
            {activeProfile.preferences.map((preference, index) => (
              <div
                key={`${preference.label}-${preference.value}-${index}`}
                className="grid grid-cols-[7rem_1fr] gap-2 rounded-md border border-[#eee8dc] bg-white px-3 py-2 text-xs"
              >
                <span className="font-mono text-neutral-500">{preference.label}</span>
                <span className="text-neutral-800">{preference.value}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="space-y-3 px-5 py-4">
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-neutral-500">
            Memory demo prompts
          </div>
          <div className="grid gap-2">
            {activeProfile.prompts.map((prompt) => (
              <Button
                key={prompt.label}
                type="button"
                variant="outline"
                className="h-auto justify-start border-[#ded8c9] bg-white px-3 py-2 text-left text-xs"
                onClick={() => submitProfilePrompt(prompt)}
                disabled={busy}
              >
                <Sparkles className="size-3.5 shrink-0" />
                <span className="min-w-0">
                  <span className="block font-medium text-neutral-950">{prompt.label}</span>
                  <span className="line-clamp-2 text-neutral-500">{prompt.prompt}</span>
                </span>
              </Button>
            ))}
          </div>
        </section>

        <section className="space-y-3 px-5 py-4">
          <div className="flex items-center justify-between gap-3">
            <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-neutral-500">
              Recent memories
            </div>
            <div className="font-mono text-[10px] text-neutral-400">
              {recentActivity.length} local
            </div>
          </div>
          {recentActivity.length ? (
            <div className="space-y-2">
              {recentActivity.map((activity) => (
                <div
                  key={activity.id}
                  className="rounded-md border border-[#eee8dc] bg-white px-3 py-2"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-mono text-[11px] uppercase text-neutral-500">
                        {activity.kind.replace("_", " ")}
                      </div>
                      <div className="mt-1 text-sm font-medium leading-5 text-neutral-950">
                        {activity.label}
                      </div>
                    </div>
                    <div className="shrink-0 font-mono text-[10px] text-neutral-400">
                      {formatActivityTime(activity.timestamp)}
                    </div>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-neutral-700">{activity.value}</p>
                  {activity.detail ? (
                    <p className="mt-1 break-words font-mono text-[10px] leading-4 text-neutral-500">
                      {activity.detail}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-md border border-dashed border-[#d1cbbb] bg-white px-3 py-5 text-center text-sm text-neutral-500">
              Run a memory prompt to show profile reads, preference writes, and
              memory-related tool calls from this browser session.
            </div>
          )}
        </section>
      </div>

      <div className="grid gap-2 border-t border-[#ded8c9] bg-white px-5 py-4 sm:grid-cols-2">
        <Button
          type="button"
          variant="outline"
          className="border-[#ded8c9] text-xs"
          onClick={reset}
        >
          <RefreshCcw className="size-3.5" />
          Reset session
        </Button>
        <Button
          type="button"
          variant="outline"
          className="border-[#ded8c9] text-xs"
          onClick={switchProfile}
        >
          <Brain className="size-3.5" />
          Switch profile
        </Button>
      </div>
    </SheetContent>
  );
}

function PromptCard({
  label,
  placeholder,
  submitLabel,
  icon,
  query,
  setQuery,
  submit,
  presets,
  disabled,
}: {
  label: string;
  placeholder: string;
  submitLabel: string;
  icon: ReactNode;
  query: string;
  setQuery: (query: string) => void;
  submit: (presetId?: string, prompt?: string) => void;
  presets: { id: string; label: string; prompt: string }[];
  disabled?: boolean;
}) {
  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submit();
  }

  return (
    <Card className="rounded-lg border-[#ded8c9] bg-white shadow-sm">
      <CardContent className="space-y-3 p-5">
        <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-neutral-500">
          {label}
        </div>
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={onSubmit}>
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={placeholder}
            className="h-11 border-[#ded8c9] bg-[#faf8f3] text-neutral-950 placeholder:text-neutral-400"
          />
          <Button
            type="submit"
            className="h-11 bg-neutral-950 text-white hover:bg-neutral-800"
            disabled={disabled || !query.trim()}
          >
            {icon}
            {submitLabel}
          </Button>
        </form>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-neutral-400">
            Try
          </span>
          {presets.map((preset) => (
            <Button
              key={preset.id}
              type="button"
              size="sm"
              variant="outline"
              className="h-7 rounded-full border-[#ded8c9] bg-[#faf8f3] px-3 font-mono text-[11px] text-neutral-700"
              onClick={() => submit(preset.id, preset.prompt)}
              disabled={disabled}
            >
              <ArrowRight className="size-3" />
              {preset.label}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyState({
  glyph,
  title,
  description,
}: {
  glyph: string;
  title: string;
  description: string;
}) {
  return (
    <Card className="rounded-lg border-dashed border-[#d1cbbb] bg-white shadow-none">
      <CardContent className="flex min-h-64 flex-col items-center justify-center p-8 text-center">
        <div className="mb-3 font-mono text-[11px] uppercase tracking-[0.2em] text-neutral-400">
          {glyph}
        </div>
        <h2 className="text-base font-semibold text-neutral-800">{title}</h2>
        <p className="mt-2 max-w-lg text-sm leading-6 text-neutral-500">{description}</p>
      </CardContent>
    </Card>
  );
}

function ProductSkeletons() {
  return (
    <div className="space-y-3">
      {[0, 1, 2].map((item) => (
        <Card key={item} className="rounded-lg border-[#ded8c9] bg-white shadow-sm">
          <CardContent className="grid gap-4 p-4 sm:grid-cols-[7.5rem_1fr_auto]">
            <Skeleton className="h-24 rounded-md" />
            <div className="space-y-3">
              <Skeleton className="h-3 w-40" />
              <Skeleton className="h-5 w-56" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
            </div>
            <Skeleton className="h-16 w-24" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function IntelligencePanel({
  response,
  progress,
  live,
}: {
  response: SearchDemoResponse | null;
  progress: number;
  live: boolean;
}) {
  if (!response) {
    return (
      <RailCard
        title="Intelligence surge"
        meta="idle"
        icon={<Activity className="size-3.5" />}
      >
        <div className="py-8 text-center text-sm text-neutral-500">
          <pre className="mb-4 font-mono text-[10px] leading-5 text-neutral-400">
            {"tool -> graph\n  \\      /\n   memory"}
          </pre>
          <p>Tool calls, graph hops, chunks, and memory writes appear here.</p>
        </div>
      </RailCard>
    );
  }

  return (
    <RailCard
      title="Intelligence surge"
      meta={live ? `${(progress / 1000).toFixed(1)}s streaming` : `${response.latencyMs}ms / ${formatNumber(response.tokens)} tok`}
      icon={<Activity className={cn("size-3.5", live && "text-emerald-600")} />}
      live={live}
    >
      <div className="divide-y divide-[#eee8dc]">
        <TraceSection title="Tools used">
          <div className="space-y-2">
            {response.tools.map((tool, index) => (
              <div
                key={`${tool.toolName}-${index}`}
                className={cn(
                  "rounded-md border border-[#eee8dc] bg-[#faf8f3] p-2 transition-opacity",
                  progress < 180 + index * 180 && live ? "opacity-30" : "opacity-100",
                )}
              >
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 grid size-4 place-items-center rounded bg-emerald-50 text-emerald-700">
                    <Check className="size-3" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="font-mono text-xs font-medium text-neutral-950">
                      {tool.toolName}
                    </div>
                    <div className="break-words font-mono text-[10px] text-neutral-500">
                      {tool.args}
                    </div>
                  </div>
                  <div className="font-mono text-[10px] text-neutral-400">
                    {formatDuration(tool.durationMs)}
                  </div>
                </div>
                <div className="ml-6 mt-1 rounded border border-[#eee8dc] bg-white px-2 py-1 font-mono text-[10px] text-neutral-700">
                  {tool.result}
                </div>
              </div>
            ))}
          </div>
        </TraceSection>

        <TraceSection title="Graph hops">
          <div className="space-y-1.5">
            {response.graphHops.map((hop, index) => (
              <div
                key={`${hop.source}-${hop.relationship}-${hop.target}-${index}`}
                className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 font-mono text-[11px]"
              >
                <span className="truncate text-right text-neutral-700">{hop.source}</span>
                <span className="rounded border border-[#ded8c9] bg-white px-1.5 py-0.5 text-[10px] text-neutral-500">
                  {hop.relationship}
                </span>
                <span className="truncate text-neutral-700">{hop.target}</span>
              </div>
            ))}
          </div>
        </TraceSection>

        <TraceSection title="Knowledge chunks">
          <div className="space-y-2">
            {response.chunks.map((chunk, index) => (
              <div key={`${chunk.title}-${index}`} className="border-t border-dashed border-[#eee8dc] pt-2 first:border-t-0 first:pt-0">
                <div className="flex items-start justify-between gap-2">
                  <div className="font-mono text-[11px] text-neutral-950">{chunk.title}</div>
                  <div className="font-mono text-[10px] text-neutral-500">
                    {chunk.score.toFixed(2)}
                  </div>
                </div>
                <p className="mt-1 text-xs italic leading-5 text-neutral-600">{chunk.snippet}</p>
              </div>
            ))}
          </div>
        </TraceSection>

        <TraceSection title="Memory writes">
          <div className="space-y-1.5">
            {response.profileWrites.map((write, index) => (
              <div key={`${write.label}-${write.value}-${index}`} className="flex gap-2 font-mono text-[11px]">
                <span className="font-semibold text-emerald-600">+</span>
                <span className="text-neutral-950">{write.label}</span>
                <span className="text-neutral-500">= {write.value}</span>
              </div>
            ))}
          </div>
        </TraceSection>
      </div>
    </RailCard>
  );
}

function RailCard({
  title,
  meta,
  icon,
  live,
  children,
}: {
  title: string;
  meta: string;
  icon: ReactNode;
  live?: boolean;
  children: ReactNode;
}) {
  return (
    <Card className="sticky top-20 overflow-hidden rounded-lg border-[#ded8c9] bg-white shadow-sm lg:max-h-[calc(100vh-7rem)] lg:overflow-auto">
      <div className="flex items-center justify-between border-b border-[#ded8c9] bg-[#faf8f3] px-4 py-3">
        <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.16em] text-neutral-950">
          <span className={cn("relative grid size-4 place-items-center", live && "animate-pulse")}>
            {icon}
          </span>
          {title}
        </div>
        <div className="font-mono text-[10px] text-neutral-500">{meta}</div>
      </div>
      <CardContent className="p-0">{children}</CardContent>
    </Card>
  );
}

function TraceSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="p-4">
      <h3 className="mb-2 font-mono text-[10px] uppercase tracking-[0.16em] text-neutral-500">
        {title}
      </h3>
      {children}
    </section>
  );
}

function SearchDemo({
  response,
  progress,
  live,
  loading,
}: {
  response: SearchDemoResponse | null;
  progress: number;
  live: boolean;
  loading: boolean;
}) {
  const showSummary = response && progress > 240;
  const showProducts = response && progress > 420;
  const showPaired = response && progress > 920;

  if (loading) {
    return <ProductSkeletons />;
  }

  if (!response) {
    return (
      <EmptyState
        glyph="answer area"
        title="Ask a question to see how the agent answers"
        description="Ask a shopping question to call the backend Agentic Commerce agent route and render the returned products, graph context, and trace details."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-lg font-semibold text-neutral-950">Top picks</h2>
        <div className="font-mono text-[11px] text-neutral-500">
          {showProducts ? `${response.picks.length} picks` : "reasoning"}
        </div>
      </div>

      <WarningList warnings={response.warnings} />

      {showSummary ? (
        <div className="max-w-3xl rounded-md border border-[#ded8c9] border-l-neutral-950 bg-white px-4 py-3 text-sm leading-6 text-neutral-700 shadow-sm">
          {response.summary}
        </div>
      ) : null}

      {showProducts ? (
        <div className="space-y-3">
          {response.picks.map((pick, index) => {
            const product = pick.product ?? products[pick.productId];
            if (!product) {
              return null;
            }
            const visible = !live || progress > 420 + index * 160;
            if (!visible) {
              return (
                <Card key={`pick-loading-${pick.productId}-${index}`} className="rounded-lg border-[#ded8c9] bg-white shadow-sm">
                  <CardContent className="p-4">
                    <Skeleton className="h-24 w-full" />
                  </CardContent>
                </Card>
              );
            }
            return (
              <ProductCardView
                key={`pick-${pick.productId}-${index}`}
                product={product}
                rank={index + 1}
                rationale={pick.why}
                signals={pick.signals}
              />
            );
          })}
        </div>
      ) : (
        <ProductSkeletons />
      )}

      {showPaired ? (
        <div className="space-y-2 pt-2">
          <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-neutral-500">
            Frequently paired / graph traversal
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {response.pairedProductIds.map((productId, index) => {
              const product = products[productId];
              return product ? <SmallProductCard key={`paired-${productId}-${index}`} product={product} /> : null;
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function SupportDemo({
  response,
  progress,
  loading,
}: {
  response: SupportDemoResponse | null;
  progress: number;
  loading: boolean;
}) {
  const showPath = response && progress > 360;
  const showActions = response && progress > 720;
  const showAlternatives = response && progress > 940;

  if (loading) {
    return <ProductSkeletons />;
  }

  if (!response) {
    return (
      <EmptyState
        glyph="diagnosis"
        title="Describe an issue to see symptom-to-solution reasoning"
        description="Describe a product issue to call the backend diagnosis route and render returned actions, citations, and trace details."
      />
    );
  }

  return (
    <Card className="rounded-lg border-[#ded8c9] bg-white shadow-sm">
      <CardContent className="space-y-5 p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 className="text-lg font-semibold text-neutral-950">Diagnosis</h2>
          <div className="font-mono text-[11px] uppercase tracking-wide text-emerald-700">
            Confidence / {response.confidence}
          </div>
        </div>

        <WarningList warnings={response.warnings} />

        <p className="max-w-3xl text-sm leading-6 text-neutral-700">{response.summary}</p>

        {showPath ? (
          <div className="grid items-stretch gap-2 lg:grid-cols-[1fr_auto_1fr_auto_1fr]">
            {response.path.map((step, index) => (
              <PathStep key={`${step.kind}-${step.label}-${index}`} step={step} isLast={index === response.path.length - 1} />
            ))}
          </div>
        ) : (
          <Skeleton className="h-24 w-full" />
        )}

        {showActions ? (
          <div className="space-y-2">
            <h3 className="font-mono text-[11px] uppercase tracking-[0.16em] text-neutral-500">
              Recommended actions
            </h3>
            <ol className="space-y-2">
              {response.actions.map((action, index) => (
                <li key={`${action}-${index}`} className="grid grid-cols-[2rem_1fr] gap-2 border-t border-[#eee8dc] pt-2 text-sm text-neutral-700 first:border-t-0 first:pt-0">
                  <span className="font-mono text-[11px] text-neutral-500">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span>{action}</span>
                </li>
              ))}
            </ol>
          </div>
        ) : null}

        {showAlternatives && response.alternativeProductIds.length ? (
          <div className="space-y-2">
            <h3 className="font-mono text-[11px] uppercase tracking-[0.16em] text-neutral-500">
              Compatible alternatives / graph: SIMILAR_TO
            </h3>
            <div className="grid gap-3 sm:grid-cols-3">
              {response.alternativeProductIds.map((productId, index) => {
                const product = products[productId];
                return product ? <SmallProductCard key={`alternative-${productId}-${index}`} product={product} /> : null;
              })}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function PathStep({
  step,
  isLast,
}: {
  step: SupportDemoResponse["path"][number];
  isLast: boolean;
}) {
  return (
    <>
      <div
        className={cn(
          "min-h-24 rounded-md border p-3",
          step.kind === "solution"
            ? "border-neutral-950 bg-neutral-950 text-white"
            : "border-[#ded8c9] bg-[#faf8f3] text-neutral-950",
        )}
      >
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] opacity-60">
          {step.kind}
        </div>
        <div className="mt-2 text-sm font-semibold leading-5">{step.label}</div>
      </div>
      {!isLast ? (
        <div className="hidden place-items-center text-neutral-400 lg:grid">
          <ArrowRight className="size-4" />
        </div>
      ) : null}
    </>
  );
}

function SourcesPanel({
  response,
  progress,
  live,
}: {
  response: SupportDemoResponse | null;
  progress: number;
  live: boolean;
}) {
  if (!response) {
    return (
      <RailCard
        title="Cited sources"
        meta="idle"
        icon={<CircleHelp className="size-3.5" />}
      >
        <div className="py-8 text-center text-sm text-neutral-500">
          <pre className="mb-4 font-mono text-[10px] leading-5 text-neutral-400">
            {"KB + ticket\n   \\  /\ndiagnosis"}
          </pre>
          <p>KB articles, support tickets, and review excerpts appear here.</p>
        </div>
      </RailCard>
    );
  }

  return (
    <RailCard
      title="Cited sources"
      meta={live ? `${(progress / 1000).toFixed(1)}s streaming` : `${response.sourceRows.length} cited`}
      icon={<Brain className={cn("size-3.5", live && "text-emerald-600")} />}
      live={live}
    >
      <div className="divide-y divide-[#eee8dc]">
        {response.sourceRows.map((source, index) => {
          const visible = !live || progress > 260 + index * 180;
          return (
            <div key={`${source.kind}-${source.id}`} className="p-4">
              {visible ? (
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded border border-blue-100 bg-blue-50 px-1.5 py-0.5 font-mono text-[10px] uppercase text-blue-800">
                      {source.kind}
                    </span>
                    <span className="font-mono text-[11px] text-neutral-950">{source.id}</span>
                  </div>
                  <div className="text-sm font-semibold text-neutral-950">{source.title}</div>
                  <p className="text-xs italic leading-5 text-neutral-600">{source.snippet}</p>
                </div>
              ) : (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-1/2" />
                  <Skeleton className="h-4 w-full" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </RailCard>
  );
}

function DemoClient() {
  const [mode, setMode] = useState<DemoMode>("search");
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<DemoResponse | null>(null);
  const [activeProfile, setActiveProfile] = useState<DemoProfile>(() => randomDemoProfile());
  const [profileChips, setProfileChips] = useState<string[]>([]);
  const [recentActivity, setRecentActivity] = useState<RecentMemoryActivity[]>([]);
  const [sessionId, setSessionId] = useState(() => newSessionId());
  const [progress, setProgress] = useState(0);
  const [live, setLive] = useState(false);
  const [loading, setLoading] = useState(false);
  const frameRef = useRef<number | null>(null);

  const searchResponse = isSearchResponse(response) ? response : null;
  const supportResponse = isSupportResponse(response) ? response : null;
  const responseLatency = response?.latencyMs ?? 0;

  const presets = useMemo(
    () =>
      mode === "search"
        ? searchSamples.map((sample) => ({
            id: sample.id,
            label: searchPresetLabels[sample.id] ?? sample.query,
            prompt: sample.query,
          }))
        : supportSamples.map((sample) => ({
            id: sample.id,
            label: supportPresetLabels[sample.id] ?? sample.query,
            prompt: sample.query,
          })),
    [mode],
  );

  useEffect(() => {
    if (!live || !responseLatency) {
      return;
    }

    const start = performance.now();
    const tick = (now: number) => {
      const elapsed = Math.min(now - start, responseLatency);
      setProgress(elapsed);
      if (elapsed < responseLatency) {
        frameRef.current = window.requestAnimationFrame(tick);
      } else {
        setLive(false);
        if (isSearchResponse(response)) {
          setProfileChips(response.profileChips);
        }
      }
    };

    frameRef.current = window.requestAnimationFrame(tick);

    return () => {
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current);
      }
    };
  }, [live, response, responseLatency]);

  function changeMode(nextMode: DemoMode) {
    setMode(nextMode);
    setResponse(null);
    setProgress(0);
    setLive(false);
    setLoading(false);
    setQuery("");
  }

  async function submit(presetId?: string, prompt?: string, modeOverride?: DemoMode) {
    const requestMode = modeOverride ?? mode;
    const nextPrompt = prompt ?? query;
    if (!nextPrompt.trim()) {
      return;
    }

    if (requestMode !== mode) {
      setMode(requestMode);
    }
    setQuery(nextPrompt);
    setLoading(true);
    setResponse(null);
    setProgress(0);
    setLive(false);

    const nextResponse = await submitDemoRequest({
      mode: requestMode,
      prompt: nextPrompt,
      presetId,
      sessionId,
      userId: activeProfile.id,
    });

    setLoading(false);
    setResponse(nextResponse);
    if (nextResponse.sessionId) {
      setSessionId(nextResponse.sessionId);
    }
    setProgress(0);
    setLive(true);
    setRecentActivity((items) =>
      [...activityFromResponse(nextResponse, nextPrompt), ...items].slice(0, 20),
    );
  }

  function reset() {
    if (frameRef.current !== null) {
      window.cancelAnimationFrame(frameRef.current);
    }
    setSessionId(newSessionId());
    setRecentActivity([]);
    setResponse(null);
    setProgress(0);
    setLive(false);
    setLoading(false);
    setQuery("");
  }

  function switchProfile() {
    if (frameRef.current !== null) {
      window.cancelAnimationFrame(frameRef.current);
    }
    setActiveProfile((current) => nextDemoProfile(current));
    setSessionId(newSessionId());
    setProfileChips([]);
    setRecentActivity([]);
    setResponse(null);
    setProgress(0);
    setLive(false);
    setLoading(false);
    setQuery("");
  }

  function submitProfilePrompt(profilePrompt: DemoProfilePrompt) {
    void submit(undefined, profilePrompt.prompt, profilePrompt.mode);
  }

  return (
    <div className="min-h-screen bg-[#f4f2ec] text-neutral-950">
      <Header
        mode={mode}
        setMode={changeMode}
        activeProfile={activeProfile}
        profileChips={profileChips}
        recentActivity={recentActivity}
        busy={loading || live}
        reset={reset}
        switchProfile={switchProfile}
        submitProfilePrompt={submitProfilePrompt}
      />

      <main className="mx-auto grid max-w-[1400px] gap-6 px-4 py-6 md:px-7 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <section className="min-w-0 space-y-5">
          <PromptCard
            label={mode === "search" ? "Ask anything about our catalog" : "Describe the problem"}
            placeholder={
              mode === "search"
                ? "e.g. waterproof trail running shoes under $150"
                : "e.g. my running shoes feel flat after 300 miles"
            }
            submitLabel={mode === "search" ? "Ask agent" : "Diagnose"}
            icon={mode === "search" ? <Send className="size-4" /> : <Sparkles className="size-4" />}
            query={query}
            setQuery={setQuery}
            submit={submit}
            presets={presets}
            disabled={loading || live}
          />

          {mode === "search" ? (
            <SearchDemo
              response={searchResponse}
              progress={progress}
              live={live}
              loading={loading}
            />
          ) : (
            <SupportDemo response={supportResponse} progress={progress} loading={loading} />
          )}
        </section>

        <aside className="min-w-0">
          {mode === "search" ? (
            <IntelligencePanel response={searchResponse} progress={progress} live={live} />
          ) : (
            <SourcesPanel response={supportResponse} progress={progress} live={live} />
          )}
        </aside>
      </main>

      <footer className="mx-auto flex max-w-[1400px] flex-wrap justify-between gap-2 border-t border-[#ded8c9] px-4 py-4 font-mono text-[11px] text-neutral-500 md:px-7">
        <span>retail/agent / demo client / v0.1</span>
        <span className="flex items-center gap-1">
          <Clock className="size-3" />
          endpoint / model-serving / chat-agent
        </span>
      </footer>
    </div>
  );
}
