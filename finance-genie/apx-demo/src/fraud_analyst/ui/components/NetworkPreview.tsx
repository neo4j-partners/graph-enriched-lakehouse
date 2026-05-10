// NetworkPreview.tsx
// Collapsible grid of ring tiles rendered above the rings table.
// Structural reference: /tmp/design-fetch/fraud-analyst/project/app.jsx (NetworkPreview).

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { RingThumb } from "@/components/RingThumb";
import { RISK_COLOR, type Risk } from "@/lib/riskColors";
import type { Topology } from "@/lib/ringLayout";
import { cn } from "@/lib/utils";

export interface NetworkPreviewRing {
  ring_id: string;
  nodes: number;
  topology: Topology;
  risk: Risk;
}

export interface NetworkPreviewProps {
  rings: NetworkPreviewRing[];
  selectedRingIds: string[];
  onToggle: (ringId: string) => void;
  defaultOpen?: boolean;
  className?: string;
}

export function NetworkPreview({
  rings,
  selectedRingIds,
  onToggle,
  defaultOpen = true,
  className,
}: NetworkPreviewProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div
      className={cn("bg-surface border border-line rounded-md", className)}
    >
      <div className="border-b border-line px-4 h-10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-ink">Graph view</span>
          <span className="text-xs text-muted-ink">
            · {rings.length} clusters
          </span>
        </div>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="inline-flex items-center justify-center h-6 w-6 rounded-sm text-muted-ink hover:text-ink hover:bg-canvas-soft transition-colors"
          aria-label={open ? "Collapse graph view" : "Expand graph view"}
          aria-expanded={open}
        >
          {open ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </button>
      </div>

      <div
        className={cn(
          "grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-2 p-3",
          !open && "hidden",
        )}
      >
        {rings.map((ring) => {
          const isSelected = selectedRingIds.includes(ring.ring_id);
          return (
            <button
              key={ring.ring_id}
              type="button"
              onClick={() => onToggle(ring.ring_id)}
              className={cn(
                "aspect-[16/10] rounded-sm border bg-canvas-soft p-1 flex flex-col items-stretch justify-between text-left transition-colors hover:bg-accent-soft",
                isSelected
                  ? "border-accent-ink ring-1 ring-accent-ink/40"
                  : "border-line-2",
              )}
              aria-pressed={isSelected}
            >
              <div className="flex-1 flex items-center justify-center min-h-0">
                <RingThumb
                  ring={ring}
                  width={88}
                  height={36}
                  selected={isSelected}
                />
              </div>
              <div className="flex items-center justify-between gap-1 px-0.5">
                <span className="font-mono text-[10px] text-muted-ink truncate">
                  {ring.ring_id}
                </span>
                <span
                  className="inline-block h-1.5 w-1.5 rounded-full shrink-0"
                  style={{ backgroundColor: RISK_COLOR[ring.risk] }}
                  aria-hidden="true"
                />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default NetworkPreview;
