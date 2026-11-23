import { useEffect, useRef, useState } from 'react'
import {
  IconBot,
  IconCheck,
  IconSend,
  IconShieldCheck,
  IconSparkles,
  IconUser,
} from '../components/Icons'
import { EmptyState } from '../components/Loading'
import { apiError } from '../services/api'
import { sendChatMessage } from '../services/llmService'

// History sent to Gemini stays small (server also caps it).
const MAX_HISTORY_SENT = 8

const SUGGESTIONS = [
  { icon: '❄️', text: 'My AC is blowing warm air. What could be the issue?' },
  { icon: '💧', text: 'My kitchen sink pipe is leaking slowly under the cabinet.' },
  { icon: '⚡', text: 'Main circuit breaker trips whenever the geyser turns on.' },
  { icon: '🐜', text: 'Best preventative measures for kitchen pest treatment?' },
]

const FRIENDLY_ERROR = 'Sorry, the AI assistant is temporarily unavailable. Please try again.'

export default function AIAssistant() {
  const [messages, setMessages] = useState([]) // [{ role: 'user'|'assistant', text, grounded, pending }]
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
      const history = outgoing
        .slice(-MAX_HISTORY_SENT)
        .map(({ role, text: t }) => ({ role, text: t.slice(0, 2000) }))
      const reply = await sendChatMessage({ message: text, history })
      setMessages([...outgoing, { role: 'assistant', text: reply.response, grounded: reply.grounded }])
    } catch (err) {
      setMessages(outgoing)
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
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: 'var(--brand)', fontWeight: 700, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
            <IconSparkles size={14} />
            <span>Smart Home Copilot</span>
          </div>
          <h1 style={{ margin: 0, fontSize: '26px' }}>AI Diagnostics Assistant</h1>
          <p className="muted small" style={{ margin: '4px 0 0' }}>
            Powered by Google Gemini with Retrieval-Augmented Generation (RAG) grounded in our platform knowledge base.
          </p>
        </div>

        {messages.length > 0 && (
          <button className="btn btn-outline btn-sm" onClick={clearConversation} disabled={busy}>
            Clear History
          </button>
        )}
      </div>

      <div className="ai-window">
        <div className="ai-scroll" ref={scrollRef}>
          {messages.length === 0 && !busy && (
            <div style={{ textAlign: 'center', padding: '30px 10px' }}>
              <div
                style={{
                  width: '54px',
                  height: '54px',
                  borderRadius: '16px',
                  background: 'var(--brand-gradient)',
                  color: '#fff',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '14px',
                  boxShadow: 'var(--shadow-primary)',
                }}
              >
                <IconBot size={28} />
              </div>
              <h3 style={{ fontSize: '18px', margin: '0 0 6px' }}>How can I help with your home today?</h3>
              <p className="muted small" style={{ maxWidth: '480px', margin: '0 auto 24px' }}>
                Describe your issue and I'll troubleshoot probable causes, safety precautions, and suggest the right professional service.
              </p>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                  gap: '10px',
                  maxWidth: '650px',
                  margin: '0 auto',
                  textAlign: 'left',
                }}
              >
                {SUGGESTIONS.map((s, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="card"
                    style={{
                      padding: '12px 14px',
                      cursor: 'pointer',
                      border: '1.5px solid var(--line)',
                      background: '#fff',
                      fontSize: '13px',
                      lineHeight: '1.4',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '10px',
                    }}
                    onClick={() => ask(s.text)}
                  >
                    <span style={{ fontSize: '18px', flexShrink: 0 }}>{s.icon}</span>
                    <span style={{ color: 'var(--ink)' }}>{s.text}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`ai-msg ${m.role}`}>
              <div className={`ai-avatar ${m.role === 'user' ? 'ai-avatar-user' : 'ai-avatar-bot'}`}>
                {m.role === 'user' ? <IconUser size={16} /> : <IconBot size={16} />}
              </div>

              <div className="ai-bubble">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: m.role === 'user' ? 'var(--brand)' : 'var(--ink)' }}>
                    {m.role === 'user' ? 'You' : 'SmartHome AI'}
                  </span>

                  {m.role === 'assistant' && m.grounded && (
                    <span className="grounded-chip" title="Grounded in platform verified technical guides">
                      <IconShieldCheck size={12} />
                      <span>Verified Knowledge</span>
                    </span>
                  )}
                </div>

                {m.pending ? (
                  <div className="ai-thinking">
                    <div className="spinner" style={{ width: '16px', height: '16px', borderWidth: '2px' }} />
                    <span>Analyzing technical knowledge base & diagnostics…</span>
                  </div>
                ) : (
                  <div style={{ whiteSpace: 'pre-wrap' }}>{m.text}</div>
                )}
              </div>
            </div>
          ))}
        </div>

        {error && (
          <div style={{ padding: '0 20px 10px' }}>
            <div className="alert alert-error" style={{ margin: 0 }}>
              {error}
            </div>
          </div>
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
            placeholder="Ask about electrical issues, AC cooling, plumbing leaks, appliance repairs…"
            value={input}
            maxLength={2000}
            disabled={busy}
            onChange={(e) => setInput(e.target.value)}
          />
          <button className="btn btn-primary" type="submit" disabled={busy || !input.trim()}>
            <IconSend size={15} />
            <span>{busy ? 'Thinking…' : 'Send'}</span>
          </button>
        </form>
      </div>
    </div>
  )
}
