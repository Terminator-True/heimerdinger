interface PlaceholderProps {
  title: string
}

// ponytail: temporary shell marker; each work unit (WU2+) replaces its route with the real view.
export function Placeholder({ title }: PlaceholderProps) {
  return (
    <main className="p-6">
      <h1 className="text-lg font-semibold text-slate-100">{title}</h1>
      <p className="mt-2 text-sm text-slate-400">Próximamente.</p>
    </main>
  )
}
