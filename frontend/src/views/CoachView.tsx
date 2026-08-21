import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowUp, Zap } from 'lucide-react'
import { askCoach } from '../lib/api'
import type { ApiError } from '../lib/api'
import { errorCopy, COACH_TIMEOUT_COPY, COACH_SERVER_COPY } from '../lib/errorCopy'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const QUICK_PROMPTS = [
  '¿En qué fallé en mi última partida?',
  '¿Cómo mejorar mi early game?',
]

// Reuse the shared errorCopy; only the coach-specific timeout/server branches
// differ (see LandingView for the same override pattern). The server string is
// untrusted and responses are rendered as plain text (whitespace-pre-wrap) —
// never via dangerouslySetInnerHTML.
function coachErrorCopy(err: ApiError): string {
  if (err.kind === 'timeout') return COACH_TIMEOUT_COPY
  if (err.kind === 'server') return COACH_SERVER_COPY
  return errorCopy(err)
}

function ThinkingDots() {
  return (
    <span className="flex items-center gap-1" aria-label="El coach está pensando">
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:0ms]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:150ms]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:300ms]" />
    </span>
  )
}

function CoachAvatar() {
  return (
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-500/15 text-amber-400">
      <Zap size={16} />
    </div>
  )
}

export function CoachView() {
  const [messages, setMessages] = useState<Message[]>([])
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [lastMatch, setLastMatch] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Derive request history from the single messages array: only committed
  // user/assistant turns. A failed user turn lives in pendingQuestion, never
  // here, so retry does not duplicate it.
  const history = messages.filter(
    (m) => m.role === 'user' || m.role === 'assistant',
  )

  useEffect(() => {
    inputRef.current?.focus()
    return () => abortRef.current?.abort()
  }, [])

  async function send(question: string) {
    const trimmed = question.trim()
    if (trimmed === '' || busy) return
    setError(null)
    setBusy(true)
    setInput('')
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const data = await askCoach(
        { question: trimmed, lastMatch, history },
        { signal: controller.signal },
      )
      const userMsg: Message = { role: 'user', content: trimmed }
      const assistantMsg: Message = { role: 'assistant', content: data.response }
      // Only on success do we commit the user turn + assistant response.
      setMessages((m) => [...m, userMsg, assistantMsg])
      setPendingQuestion(null)
    } catch (err) {
      if (!controller.signal.aborted) {
        // Keep the failed turn out of messages/history; stash it for retry.
        setPendingQuestion(trimmed)
        setError(coachErrorCopy(err as ApiError))
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null
      setBusy(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void send(input)
  }

  return (
    <main className="mx-auto flex min-h-[calc(100vh-3.5rem)] w-full max-w-3xl flex-col px-4 py-4 sm:px-6">
      {/* Header del chat */}
      <header className="mb-4 flex items-center gap-3 border-b border-slate-800 pb-3">
        <CoachAvatar />
        <div className="flex flex-col">
          <h1 className="text-sm font-semibold text-slate-100">Coach IA</h1>
          <span className="flex items-center gap-1.5 text-xs text-slate-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Asistente de Heimerdinger
          </span>
        </div>
      </header>

      {/* Mensajes */}
      <div className="flex-1 space-y-6">
        {messages.length === 0 && !busy && (
          <div className="flex flex-col gap-3 pt-8">
            <CoachAvatar />
            <p className="text-sm text-slate-300">
              Hola, soy tu coach. Preguntame sobre tu rendimiento, partidas o
              cómo mejorar tu juego.
            </p>
            <div className="flex flex-wrap gap-2">
              {QUICK_PROMPTS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => void send(p)}
                  className="rounded-full border border-slate-800 px-3 py-1.5 text-sm text-slate-300 hover:border-amber-500/40 hover:bg-slate-900 hover:text-amber-400"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) =>
          msg.role === 'user' ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-blue-700 px-4 py-2.5 text-sm text-white">
                {msg.content}
              </div>
            </div>
          ) : (
            <div key={i} className="flex gap-3">
              <CoachAvatar />
              <div className="whitespace-pre-wrap rounded-2xl rounded-tl-sm bg-slate-900 px-4 py-2.5 text-sm text-slate-100">
                {msg.content}
              </div>
            </div>
          ),
        )}

        {busy && (
          <div className="flex gap-3">
            <CoachAvatar />
            <div className="rounded-2xl rounded-tl-sm bg-slate-900 px-4 py-3">
              <ThinkingDots />
            </div>
          </div>
        )}
      </div>

      {/* Error */}
      {error !== null && (
        <div className="mt-4 flex items-center justify-between gap-4 rounded-lg border border-red-900 bg-red-950 p-3">
          <p className="text-sm text-red-400">{error}</p>
          {pendingQuestion !== null && (
            <button
              type="button"
              onClick={() => void send(pendingQuestion)}
              className="rounded border border-slate-800 px-3 py-1 text-sm text-amber-500 hover:bg-slate-800"
            >
              Reintentar
            </button>
          )}
        </div>
      )}

      {/* Toggle + input */}
      <div className="sticky bottom-4 mt-4 space-y-2">
        <label className="flex items-center gap-2 text-sm text-slate-400">
          <input
            type="checkbox"
            checked={lastMatch}
            onChange={(e) => setLastMatch(e.target.checked)}
            className="accent-blue-600"
          />
          Incluir mi última partida
          <span className="text-xs text-slate-500">
            (puede ser la de cualquier jugador del roster)
          </span>
        </label>

        <form
          onSubmit={onSubmit}
          className="flex items-end gap-2 rounded-2xl border border-slate-700 bg-slate-900 p-2 focus-within:border-amber-500/50"
        >
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Escribí tu pregunta…"
            aria-label="Pregunta"
            className="flex-1 bg-transparent px-2 py-2 text-sm text-slate-100 placeholder-slate-500 outline-none"
          />
          <button
            type="submit"
            disabled={busy || input.trim() === ''}
            aria-label="Enviar pregunta"
            className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500 text-slate-950 transition-colors hover:bg-amber-400 disabled:opacity-40"
          >
            <ArrowUp size={18} />
          </button>
        </form>
      </div>
    </main>
  )
}
