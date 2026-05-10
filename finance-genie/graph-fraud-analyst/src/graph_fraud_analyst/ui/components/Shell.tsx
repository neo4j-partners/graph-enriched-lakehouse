import type * as React from "react";
import { cn } from "@/lib/utils";
import { Stepper, type Step } from "./Stepper";

export interface ShellProps {
  step: Step;
  onJump?: (step: Step) => void;
  user?: string;
  children: React.ReactNode;
  className?: string;
}

function BrandMark() {
  return (
    <svg
      width={18}
      height={18}
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.25}
      className="text-ink"
      aria-hidden="true"
    >
      <rect x={1} y={1} width={16} height={16} />
      <line x1={1} y1={17} x2={17} y2={1} />
    </svg>
  );
}

export function Shell({ step, onJump, user, children, className }: ShellProps) {
  return (
    <div
      className={cn(
        "min-h-screen bg-canvas text-ink flex flex-col",
        className,
      )}
    >
      <header className="sticky top-0 z-20 bg-canvas/85 backdrop-blur border-b border-line">
        <div className="mx-auto w-full max-w-7xl px-6 h-12 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BrandMark />
            <span className="text-sm font-semibold tracking-tight">
              Fraud Signal Workbench
            </span>
          </div>
          {user && (
            <span className="text-xs text-muted-ink">{user}</span>
          )}
        </div>
      </header>
      <div className="border-b border-line bg-canvas">
        <div className="mx-auto w-full max-w-7xl px-6 h-12 flex items-center">
          <Stepper current={step} onJump={onJump} />
        </div>
      </div>
      <main className="mx-auto w-full max-w-7xl px-6 py-6 flex-1">
        {children}
      </main>
    </div>
  );
}

export default Shell;
