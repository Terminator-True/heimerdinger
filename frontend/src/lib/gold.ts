// Pure helpers for gold views. Kept framework-free so badge hide-logic and
// flat-key chart mapping are unit-testable without rendering.

// Efficiency ratio = goldEarned / items.gold_value, computed client-side.
// Returns null (badge must be HIDDEN) when either side is absent after
// parsing OR gold_value is 0 (0 == unknown, never divide by it).
export interface GoldEfficiencySource {
  goldEarned?: number | null
  items?: { gold_value?: number | null }
}

export function goldEfficiency(row: GoldEfficiencySource): number | null {
  const earned = row.goldEarned
  const value = row.items?.gold_value
  if (
    typeof earned !== 'number' ||
    typeof value !== 'number' ||
    value === 0 ||
    !Number.isFinite(earned) ||
    !Number.isFinite(value)
  ) {
    return null
  }
  return earned / value
}

// Map the FLAT aggregate_gold keys to a chart-friendly series. Only metrics
// with a numeric value are included — a metric that the backend omitted (no
// samples) or returned as null is skipped entirely. Input is a loose record:
// the zod passthrough output of aggregateGoldSchema is an index-signature
// object, so a strict shape would reject it.
export type ChartPoint = { label: string; value: number }

export function goldEarnedSeries(agg: Record<string, unknown>): ChartPoint[] {
  const entries: Array<[string, unknown]> = [
    ['Media', agg['goldEarned']],
    ['Mediana', agg['goldEarned_median']],
    ['P25', agg['goldEarned_p25']],
    ['P75', agg['goldEarned_p75']],
  ]
  const out: ChartPoint[] = []
  for (const [label, value] of entries) {
    if (typeof value === 'number') out.push({ label, value })
  }
  return out
}
