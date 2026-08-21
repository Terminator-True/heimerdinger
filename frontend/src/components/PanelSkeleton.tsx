import { Skeleton } from './Skeleton'

// Shared per-panel loading state for data views (WU2+). Identical markup was
// duplicated in GoldReportView and MatchDetailView; PlayerDashboardView keeps
// its own richer variant.
export function PanelSkeleton() {
  return (
    <div aria-label="Cargando" className="flex flex-col gap-2 rounded border border-slate-800 bg-slate-900 p-6">
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-full" />
    </div>
  )
}
