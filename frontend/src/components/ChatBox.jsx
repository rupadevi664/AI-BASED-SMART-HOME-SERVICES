import { useEffect, useRef, useState } from 'react'
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
            // WS frames carry no DB id — dedupe on content+sender+timestamp
            // (REST history rows use created_at, WS frames use timestamp).
            setMessages((prev) => {
              if (ev.id != null && prev.some((m) => m.id === ev.id)) return prev
              const key = `${ev.sender_id}|${ev.timestamp}|${ev.message}`
              if (prev.some((m) => `${m.sender_id}|${m.timestamp || m.created_at}|${m.message}` === key)) return prev
              return [...prev, ev]
            })
          } else if (ev.type === 'user_joined') {
            setSystem((s) => [...s, `User #${ev.user_id} joined`])
          } else if (ev.type === 'user_left') {
            setSystem((s) => [...s, `User #${ev.user_id} left`])
          } else if (ev.type === 'error') {
            setNotice(ev.message)
          } else if (ev.type === 'ws_gave_up') {
            setNotice('Live connection unavailable — showing history only. Retry from the bookings page.')
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
    connected: ['chip-ok', 'Live'],
    connecting: ['chip-warn', 'Connecting…'],
    closed: ['chip-warn', 'Reconnecting…'],
    error: ['chip-err', 'Connection error'],
  }[status] || ['chip-warn', status]

  return (
    <div className="chat-wrap card">
      <div className="card-head">
        <div>
          <h3>Chat — Booking #{bookingId}</h3>
          {booking && (
            <p className="muted small">
              {booking.service_name} · {booking.status}
            </p>
          )}
        </div>
        <span className={`chip ${statusChip[0]}`}>{statusChip[1]}</span>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="chat-scroll">
        {messages.length === 0 && system.length === 0 && !error && (
          <p className="muted center">No messages yet — say hello 👋</p>
        )}
        {messages.map((m, i) => {
          const mine = m.sender_id === user?.id
          return (
            <div key={m.id || `m${i}`} className={`bubble ${mine ? 'mine' : 'theirs'}`}>
              <div className="bubble-meta">
                {mine ? 'You' : `User #${m.sender_id}`}
                {m.sender_role ? ` · ${m.sender_role}` : ''} ·{' '}
                {new Date(m.timestamp || m.created_at).toLocaleTimeString()}
              </div>
              {m.message || m.text}
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
          placeholder={status === 'connected' ? 'Type a message…' : 'Waiting for connection…'}
          maxLength={2000}
          disabled={status !== 'connected'}
        />
        <button className="btn btn-primary" disabled={status !== 'connected' || !text.trim()}>
          Send
        </button>
      </form>
      <p className="muted tiny">
        Messages persist server-side; history loads via GET /bookings/{bookingId}/messages.
      </p>
    </div>
  )
}
