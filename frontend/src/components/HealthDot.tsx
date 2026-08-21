import { useHealthPoll, type HealthStatus } from '../hooks/useHealthPoll'

const LABELS: Record<HealthStatus, { text: string; className: string }> = {
  online: { text: 'Conectado', className: 'bg-emerald-500' },
  degraded: { text: 'Degradado', className: 'bg-amber-500' },
  offline: { text: 'Sin conexión', className: 'bg-red-400' },
}

export function HealthDot() {
  const { status } = useHealthPoll()
  const label = LABELS[status]
  return (
    <span className="flex items-center gap-2 text-xs text-slate-300">
      <span className={`inline-block h-2 w-2 rounded-full ${label.className}`} />
      {label.text}
    </span>
  )
}
