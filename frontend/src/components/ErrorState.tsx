// ponytail: consumed by WU2+ data views (design §hook pattern)
interface ErrorStateProps {
  message: string
  onRetry: () => void
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex items-center justify-center gap-4 rounded border border-slate-800 bg-slate-900 p-6">
      <p className="text-sm text-red-400">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded border border-slate-800 px-3 py-1 text-sm text-amber-500 hover:bg-slate-800"
      >
        Reintentar
      </button>
    </div>
  )
}
