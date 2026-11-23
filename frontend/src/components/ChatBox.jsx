import { useEffect, useRef, useState } from 'react'
import { IconChat, IconClock, IconSend, IconShieldCheck } from './Icons'
import { useAuth } from '../context/AuthContext'
import { apiError } from '../services/api'
import { getBooking } from '../services/bookingService'
import { getMessages } from '../services/messageService'
import { BookingSocket } from '../services/websocketService'

/** Booking chat: history from REST, live frames from the Phase 4 WebSocket. */
export default function ChatBox({ bookingId }) {
  const { token, user } = useAuth()
  const [booking, setBooking] = useState(null)
  const [messages, setMessages] = useState([])
  const [system, setSystem] = useState([])
  const [text, setText] = useState('')
  const [status, setStatus] = useState('connecting')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const socketRef = useRef(null)
  const bottomRef = useRef(null)

  // Load booking (for header/status) + persisted history, then open the WS.
  useEffect(() => {
    if (!bookingId || !token) return
    let socket
    let cancelled = false

    async function boot() {
      try {
        const [b, history] = await Promise.all([getBooking(bookingId), getMessages(bookingId)])
        if (cancelled) return
        setBooking(b)
        setMessages(history)
      } catch (err) {
        if (!cancelled) setError(apiError(err))
      }

      socket = new BookingSocket({
        bookingId: Number(bookingId),
        token,
        channel: 'chat',
        onEvent: (ev) => {
          if (cancelled) return
          if (ev.type === 'message') {
            setMessages((prev) => {
              if (ev.id != null && prev.some((m) => m.id === ev.id)) return prev
              const key = `${ev.sender_id}|${ev.timestamp}|${ev.message}`
              if (
                prev.some(
                  (m) => `${m.sender_id}|${m.timestamp || m.created_at}|${m.message}` === key,
                )
              )
                return prev
              return [...prev, ev]
            })
          } else if (ev.type === 'user_joined') {
            setSystem((s) => [...s, `User #${ev.user_id} joined the room`])
          } else if (ev.type === 'user_left') {
            setSystem((s) => [...s, `User #${ev.user_id} left the room`])
          } else if (ev.type === 'error') {
            setNotice(ev.message)
          } else if (ev.type === 'ws_gave_up') {
            setNotice('Live connection unavailable — showing history only.')
          }
        },
        onStatus: setStatus,
      })
      socket.connect()
      socketRef.current = socket
    }
    boot()
    return () => {
      cancelled = true
      socket?.stop()
    }
  }, [bookingId, token])

  // Auto-scroll to the newest message.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, system])

  function send(e) {
    e.preventDefault()
    const msg = text.trim()
    if (!msg || msg.length > 2000) return
    socketRef.current?.send({ type: 'message', message: msg })
    setText('')
    setNotice('')
  }

  const statusChip = {
    connected: ['badge-accepted', 'Live Channel'],
    connecting: ['badge-pending', 'Connecting…'],
    closed: ['badge-pending', 'Reconnecting…'],
    error: ['badge-rejected', 'Offline'],
  }[status] || ['badge-pending', status]

  return (
    <div className="chat-wrap card">
      <div className="card-head" style={{ borderBottom: '1px solid var(--line)', paddingBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: 'var(--brand-light)',
              color: 'var(--brand)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <IconChat size={20} />
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: '17px' }}>Booking #{bookingId} Chat</h3>
            {booking && (
              <p className="muted tiny" style={{ margin: 0 }}>
                {booking.service_name} · Status: <strong>{booking.status}</strong>
              </p>
            )}
          </div>
        </div>

        <span className={`badge ${statusChip[0]}`}>
          <span className="badge-dot" />
          <span>{statusChip[1]}</span>
        </span>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="chat-scroll">
        {messages.length === 0 && system.length === 0 && !error && (
          <div className="state" style={{ background: 'transparent', border: 'none', padding: '40px 10px' }}>
            <span style={{ fontSize: '32px', display: 'block', marginBottom: '8px' }}>💬</span>
            <strong>No messages yet</strong>
            <p className="muted small">Start the conversation with your service counterpart.</p>
          </div>
        )}

        {messages.map((m, i) => {
          const mine = m.sender_id === user?.id
          const time = new Date(m.timestamp || m.created_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })
          return (
            <div key={m.id || `m${i}`} className={`bubble ${mine ? 'mine' : 'theirs'}`}>
              <div className="bubble-meta">
                {mine ? 'You' : `User #${m.sender_id}`}
                {m.sender_role ? ` (${m.sender_role})` : ''} · {time}
              </div>
              <div style={{ wordBreak: 'break-word' }}>{m.message || m.text}</div>
            </div>
          )
        })}

        {system.map((s, i) => (
          <div key={`s${i}`} className="system-line">
            {s}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {notice && <div className="alert alert-warn">{notice}</div>}

      <form className="chat-input" onSubmit={send}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={status === 'connected' ? 'Type a secure message…' : 'Waiting for connection…'}
          maxLength={2000}
          disabled={status !== 'connected'}
        />
        <button className="btn btn-primary" disabled={status !== 'connected' || !text.trim()}>
          <IconSend size={15} />
          <span>Send</span>
        </button>
      </form>
    </div>
  )
}
