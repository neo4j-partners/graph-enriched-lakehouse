// riskColors.ts
// Risk palette helpers for the Fraud Analyst UI.
// Exposes CSS var() strings for SVG attributes, Tailwind classes for pills and
// badges, and a score-to-band mapper used across screens and table rows.

export type Risk = 'H' | 'M' | 'L';

export const RISK_COLOR: Record<Risk, string> = {
  H: 'var(--color-risk-high)',
  M: 'var(--color-risk-med)',
  L: 'var(--color-risk-low)',
};

export const NODE_INK: string = 'var(--color-ink-2)';
export const NODE_INK_DIM: string = 'var(--color-line-3)';

export function scoreToRisk(score: number): Risk {
  if (score >= 0.75) return 'H';
  if (score >= 0.5) return 'M';
  return 'L';
}

export const RISK_BG_CLASS: Record<Risk, string> = {
  H: 'bg-risk-high/15',
  M: 'bg-risk-med/15',
  L: 'bg-risk-low/15',
};

export const RISK_TEXT_CLASS: Record<Risk, string> = {
  H: 'text-risk-high',
  M: 'text-risk-med',
  L: 'text-risk-low',
};

export const RISK_LABEL: Record<Risk, string> = {
  H: 'High',
  M: 'Medium',
  L: 'Low',
};

export type RiskPillIntent = 'risk-high' | 'risk-med' | 'risk-low';

export const RISK_PILL_INTENT: Record<Risk, RiskPillIntent> = {
  H: 'risk-high',
  M: 'risk-med',
  L: 'risk-low',
};
