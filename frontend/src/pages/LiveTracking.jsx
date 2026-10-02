import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import LiveMap from '../components/LiveMap'
import { EmptyState, ErrorState, Spinner } from '../components/Loading'
import { useAuth } from '../context/AuthContext'
import { apiError } from '../services/api'
import { getBooking, getLatestLocation, getLocationHistory } from '../services/bookingService'
import { BookingSocket } from '../services/websocketService'
import useGeolocation from '../hooks/useGeolocation'

/**
 * Live tracking for one booking.
 * - Customer: watches the expert's marker move in real time (Phase 5 WS).
 * - Expert: Start/Stop Location Sharing → watchPosition → throttled
 *   location_update frames over the same WS; server enforces authorization.
 */
export default function LiveTracking() {
  const { bookingId } = useParams()
  const { token, isExpert } = useAuth()
  const navigate = useNavigate()
  const geo = useGeolocation()

  const socketRef = useRef(null)
  const lastSentRef = useRef(0)

  const [booking, setBooking] = useState(null)
  const [expertPos, setExpertPos] = useState(null)
  const [customerPos, setCustomerPos] = useState(null)
  const [status, setStatus] = useState('connecting')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [sharing, setSharing] = useState(false)
  const [sentCount, setSentCount] = useState(0)
  const [loaded, setLoaded] = useState(false)

  // Boot: booking guard + REST seed (latest fix/history), then open the WS.
  useEffect(() => {
    if (!token) return
    let cancelled = false

    async function boot() {
      try {
        const b = await getBooking(bookingId)
        if (cancelled) return
        setBooking(b)
        if (b.status !== 'ACCEPTED') {
          setLoaded(true)
          return // server would reject the socket anyway (4409)
        }
        // Seed the map from REST: latest fix, else last history point.
        try {
          const latest = await getLatestLocation(bookingId)
          if (!cancelled && latest) setExpertPos({ lat: latest.latitude, lng: latest.longitude })
        } catch {
          /* NO_LOCATION_AVAILABLE — fine, map just waits for live frames */
        }
        if (!cancelled && !expertPos) {
          try {
            const hist = await getLocationHistory(bookingId, 50)
            const last = hist?.points?.[hist.points.length - 1]
            if (last) setExpertPos({ lat: last.latitude, lng: last.longitude })
          } catch {
            /* ignore */
          }
        }

        const socket = new BookingSocket({
          bookingId: Number(bookingId),
          token,
          channel: 'location',
          onEvent: (ev) => {
            if (cancelled) return
            if (ev.type === 'location_update') {
              setExpertPos({ lat: ev.latitude, lng: ev.longitude })
            } else if (ev.type === 'connected') {
              setNotice(ev.role === 'expert' ? 'Channel open — you can share your location below.' : 'Channel open — watching the expert live.')
            } else if (ev.type === 'error') {
              setNotice(ev.message)
            }
          },
          onStatus: setStatus,
        })
        socket.connect()
        socketRef.current = socket
      } catch (err) {
        if (!cancelled) setError(apiError(err))
      } finally {
        if (!cancelled) setLoaded(true)
      }
    }
    boot()
    return () => {
      cancelled = true
      socketRef.current?.stop()
      socketRef.current = null
      geo.stopWatch()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookingId, token])

  // Customer: show their own position as the home marker (best effort).
  useEffect(() => {
    if (!loaded || isExpert) return
    geo.locate().then((p) => setCustomerPos({ lat: p.lat, lng: p.lng })).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, isExpert])

  // Expert sharing: watchPosition → send frames no faster than ~1/s.
  useEffect(() => {
    if (!sharing || !isExpert) return
    geo.watch()
    const timer = setInterval(() => {
      const p = geo.position
      const socket = socketRef.current
      if (!p || !socket || socket.ws?.readyState !== WebSocket.OPEN) return
      if (Date.now() - lastSentRef.current < 1100) return // respect the 1s server throttle
      lastSentRef.current = Date.now()
      socket.send({
        type: 'location_update',
        latitude: p.lat,
        longitude: p.lng,
        accuracy: p.accuracy ?? null,
        timestamp: new Date().toISOString(),
      })
      setSentCount((c) => c + 1)
    }, 700)
    return () => {
      clearInterval(timer)
      geo.stopWatch()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sharing, isExpert, geo.position])

  function stopSharing() {
    setSharing(false)
    geo.stopWatch()
  }

  const statusChip = {
    connected: ['chip-ok', 'Live'],
    connecting: ['chip-warn', 'Connecting…'],
    closed: ['chip-warn', 'Reconnecting…'],
    error: ['chip-err', 'Connection error'],
  }[status] || ['chip-warn', status]

  if (error) {
    return (
      <div className="page">
        <ErrorState message={error} onRetry={() => window.location.reload()} />
      </div>
    )
  }
  if (!loaded) {
    return (
      <div className="page page-center">
        <Spinner label="Opening tracking…" />
      </div>
    )
  }
  if (booking && booking.status !== 'ACCEPTED') {
    return (
      <div className="page">
        <EmptyState
          title="Live tracking needs an ACCEPTED booking"
          hint={`Booking #${bookingId} is ${booking.status}. Tracking is only available for accepted jobs (server rule).`}
        >
          <button className="btn btn-primary btn-sm" onClick={() => navigate(-1)}>Go back</button>
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="page">
      <button className="btn btn-outline btn-sm" onClick={() => navigate(-1)}>← Back</button>
      <div className="track-head">
        <h1>Live tracking — Booking #{bookingId}</h1>
        <span className={`chip ${statusChip[0]}`}>{statusChip[1]}</span>
      </div>
      {booking && (
        <p className="muted small">
          {booking.service_name} · {booking.scheduled_date} {booking.scheduled_time?.slice(0, 5)} ·{' '}
          {booking.service_address}
        </p>
      )}

      {notice && <div className="alert alert-warn">{notice}</div>}

      {isExpert ? (
        <div className="card share-card">
          <div className="share-row">
            <div>
              <strong>Location sharing {sharing ? 'is ON' : 'is OFF'}</strong>
              <p className="muted tiny">
                {sharing
                  ? `Streaming your GPS (${sentCount} update${sentCount === 1 ? '' : 's'} sent) — the customer sees the marker move.`
                  : 'Start sharing while heading to the job; the customer watches your marker in real time.'}
              </p>
              {geo.error && <p className="danger tiny">{geo.error}</p>}
              {sharing && geo.position && (
                <p className="mono tiny">
                  {geo.position.lat.toFixed(6)}, {geo.position.lng.toFixed(6)}
                </p>
              )}
            </div>
            {sharing ? (
              <button className="btn btn-danger" onClick={stopSharing}>■ Stop Location Sharing</button>
            ) : (
              <button className="btn btn-primary" onClick={() => setSharing(true)}>▶ Start Location Sharing</button>
            )}
          </div>
        </div>
      ) : (
        <p className="muted small">
          Watching the assigned expert's marker — it moves automatically as they travel, no refresh needed.
        </p>
      )}

      <LiveMap customerPos={customerPos} expertPos={expertPos} height={420} />

      <div className="map-legend muted tiny">🏠 your position · 🛠️ expert's live position</div>
    </div>
  )
}
