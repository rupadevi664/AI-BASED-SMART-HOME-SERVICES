import { useEffect, useRef, useState } from 'react'
import { EmptyState } from '../components/Loading'
import { apiError } from '../services/api'
import { sendChatMessage } from '../services/llmService'

// History sent to Gemini stays small (server also caps it).
const MAX_HISTORY_SENT = 8

const SUGGESTIONS = [
  'My AC is not cooling. What could be the problem?',
  'My kitchen tap is leaking. What should I do?',
  'Which service should I book for wiring problems?',
]

const FRIENDLY_ERROR = 'Sorry, the AI assistant is temporarily unavailable. Please try again.'

export default function AIAssistant() {
  const [messages, setMessages] = useState([]) // [{ role: 'user'|'assistant', text }]
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const scrollRef = useRef(null)

  // Keep the newest message in view.
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, busy])

  async function ask(question) {
    const text = (question ?? input).trim()
    if (!text || busy) return

    setError('')
    setInput('')
    const outgoing = [...messages, { role: 'user', text }]
    setMessages([...outgoing, { role: 'assistant', text: '', pending: true }])
    setBusy(true)

    try {
      // Send only the last few turns — Phase 7 keeps memory simple,
      // no persistence.
      const history = outgoing
        .slice(-MAX_HISTORY_SENT)
        .map(({ role, text: t }) => ({ role, text: t }))
      const reply = await sendChatMessage({ message: text, history })
      setMessages([...outgoing, { role: 'assistant', text: reply }])
    } catch (err) {
      setMessages(outgoing) // drop the pending bubble, keep the question
      setError(apiError(err) || FRIENDLY_ERROR)
    } finally {
      setBusy(false)
    }
  }

  function clearConversation() {
    setMessages([])
    setError('')
  }

  return (
    <div className="page ai-page">
      <div className="ai-head">
        <h1>Smart Home AI Assistant</h1>
        {messages.length > 0 && (
          <button className="btn btn-outline btn-sm" onClick={clearConversation} disabled={busy}>
            Clear conversation
          </button>
        )}
      </div>
      <p className="muted small">
        General guidance for home-service problems — the assistant suggests a service
        category, but bookings always go through the normal booking flow.
      </p>

      <div className="card ai-window">
        <div className="chat-scroll ai-scroll" ref={scrollRef}>
          {messages.length === 0 && !busy && (
            <EmptyState
              title="Ask me anything about your home"
              hint="Describe the problem and I'll point you to the right service category."
            >
              <div className="ai-suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="chip" disabled={busy} onClick={() => ask(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </EmptyState>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.role === 'user' ? 'mine' : 'theirs'}`}>
              <div className="bubble-meta">{m.role === 'user' ? 'You' : 'AI Assistant'}</div>
              {m.pending ? <span className="ai-thinking">Thinking…</span> : m.text}
            </div>
          ))}
        </div>

        {error && (
          <p className="danger small ai-error" role="alert">
            {error}
          </p>
        )}

        <form
          className="chat-input"
          onSubmit={(e) => {
            e.preventDefault()
            ask()
          }}
        >
          <input
            type="text"
            placeholder="Type your question… e.g. My washing machine is not working"
            value={input}
            maxLength={2000}
            disabled={busy}
            onChange={(e) => setInput(e.target.value)}
          />
          <button className="btn btn-primary" type="submit" disabled={busy || !input.trim()}>
            {busy ? 'Thinking…' : 'Send'}
          </button>
        </form>
      </div>
    </div>
  )
}
