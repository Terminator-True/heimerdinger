// ponytail: consumed by WU2+ data views (design §hook pattern)
interface SkeletonProps {
  className?: string
}

export function Skeleton({ className = '' }: SkeletonProps) {
  return <div className={`animate-pulse rounded bg-slate-800 ${className}`} />
}
