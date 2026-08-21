import { useState, type FormEvent } from 'react'
import { askCoach } from '../lib/api'
import type { ApiError } from '../lib/api'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const QUICK_PROMPTS = [
  '¿En qué fallé en mi última partida?',
  '¿Cómo mejorar mi early game?',
]

// Coach-specific error copy. The server string is untrusted and responses are
// rendered as plain text (whitespace-pre-wrap) — never via dangerouslySetInnerHTML.
function coachErrorCopy(err: ApiError): string {
  switch (err.kind) {
    case 'timeout':
      return 'Ollama tardó demasiado. Probá de nuevo.'
    case 'server':
      return 'Verificá que Ollama esté corriendo localmente.'
    case 'auth':
      return 'Se requiere una API key. Configurala en Ajustes.'
    case 'network':
      return 'No hay conexión con el backend. Verificá que esté corriendo.'
    default:
      return 'Ocurrió un error inesperado.'
  }
}

export function CoachView() {
  const [messages, setMessages] = useState<Message[]>([])
  const [history, setHistory] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [lastMatch, setLastMatch] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function send(question: string) {
    const trimmed = question.trim()
    if (trimmed === '' || busy) return
    setError(null)
    setBusy(true)
    const userMsg: Message = { role: 'user', content: trimmed }
    setMessages((m) => [...m, userMsg])
    setHistory((h) => [...h, userMsg])
    setInput('')
    try {
      const data = await askCoach({ question: trimmed, lastMatch, history })
      const assistantMsg: Message = { role: 'assistant', content: data.response }
      setMessages((m) => [...m, assistantMsg])
      setHistory((h) => [...h, assistantMsg])
    } catch (err) {
      // Prior conversation stays intact on error.
      setError(coachErrorCopy(err as ApiError))
    } finally {
      setBusy(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void send(input)
  }

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-4 p-6">
      <h1 className="text-xl font-semibold text-slate-100">Coach IA</h1>

      <div className="flex flex-col gap-3 rounded border border-slate-800 bg-slate-900 p-4">
        {messages.length === 0 && (
          <p className="text-sm text-slate-400">
            Preguntale al coach sobre tu rendimiento.
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`whitespace-pre-wrap rounded px-3 py-2 text-sm ${
              msg.role === 'user'
                ? 'self-end bg-blue-900 text-slate-100'
                : 'self-start bg-slate-800 text-slate-100'
            }`}
          >
            {msg.content}
          </div>
        ))}
        {busy && <p className="text-sm text-slate-400">El coach está pensando…</p>}
      </div>

      {error !== null && (
        <div className="flex items-center justify-between gap-4 rounded border border-red-900 bg-red-950 p-3">
          <p className="text-sm text-red-400">{error}</p>
          {history.length > 0 && (
            <button
              type="button"
              onClick={() => void send(history[history.length - 1]!.content)}
              className="rounded border border-slate-800 px-3 py-1 text-sm text-amber-500 hover:bg-slate-800"
            >
              Reintentar
            </button>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {QUICK_PROMPTS.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => void send(p)}
            className="rounded border border-slate-800 px-3 py-1 text-sm text-slate-300 hover:bg-slate-800"
          >
            {p}
          </button>
        ))}
      </div>

      <label className="flex items-center gap-2 text-sm text-slate-400">
        <input
          type="checkbox"
          checked={lastMatch}
          onChange={(e) => setLastMatch(e.target.checked)}
          className="accent-blue-600"
        />
        Incluir mi última partida
      </label>
      <p className="text-xs text-slate-500">
        La respuesta puede referirse a la última partida de cualquier jugador del
        roster, no necesariamente la tuya.
      </p>

      <form onSubmit={onSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Escribí tu pregunta…"
          aria-label="Pregunta"
          className="flex-1 rounded border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder-slate-500"
        />
        <button
          type="submit"
          disabled={busy || input.trim() === ''}
          className="rounded bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:opacity-50"
        >
          Enviar
        </button>
      </form>
    </main>
  )
}
