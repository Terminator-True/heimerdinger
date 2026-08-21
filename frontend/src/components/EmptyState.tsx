interface EmptyStateProps {
  message: string
}

export function EmptyState({ message }: EmptyStateProps) {
  return (
    <div className="flex items-center justify-center rounded border border-slate-800 bg-slate-900 p-6">
      <p className="text-sm text-slate-400">{message}</p>
    </div>
  )
}
