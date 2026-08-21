// Shared display formatting for metric values across dashboard views.
export function fmtValue(v: unknown): string {
  if (v === undefined || v === null || v === '') return '—'
  return String(v)
}
