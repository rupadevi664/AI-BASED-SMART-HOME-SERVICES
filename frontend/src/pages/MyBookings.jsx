import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import BookingCard from '../components/BookingCard'
import { EmptyState, ErrorState, Spinner } from '../components/Loading'
import PayNow from '../components/PayNow'
import ReviewWidget from '../components/ReviewWidget'
import { apiError } from '../services/api'
import { cancelBooking, getMyBookings } from '../services/bookingService'

const FILTERS = ['ALL', 'PENDING', 'ACCEPTED', 'COMPLETED', 'CANCELLED', 'REJECTED']

export default function MyBookings() {
  const navigate = useNavigate()
  const [bookings, setBookings] = useState(null)
  const [filter, setFilter] = useState('ALL')
  const [error, setError] = useState('')
  const [flash, setFlash] = useState('')
  const [busyId, setBusyId] = useState(null)

  async function load() {
    setError('')
    try {
      setBookings(await getMyBookings())
    } catch (err) {
      setError(apiError(err))
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function onAction(key, booking) {
    if (key === 'chat') return navigate(`/customer/bookings/${booking.id}/chat`)
    if (key === 'track') return navigate(`/customer/bookings/${booking.id}/tracking`)
    if (key === 'cancel') {
      const reason = window.prompt('Cancellation reason (min 3 characters):')
      if (!reason || reason.trim().length < 3) return
      setBusyId(booking.id)
      try {
        await cancelBooking(booking.id, reason.trim())
        setFlash(`Booking #${booking.id} cancelled.`)
        await load()
      } catch (err) {
        setFlash('')
        setError(apiError(err))
      } finally {
        setBusyId(null)
      }
    }
  }

  function actionsFor(b) {
    const acts = [{ key: 'chat', label: '💬 Chat', kind: 'btn-secondary' }]
    if (b.status === 'PENDING') acts.push({ key: 'cancel', label: 'Cancel', kind: 'btn-danger', disabled: busyId === b.id })
    if (b.status === 'ACCEPTED') acts.push({ key: 'track', label: '🗺 Track expert' })
    return acts
  }

  const visible = (bookings || []).filter((b) => filter === 'ALL' || b.status === filter)

  return (
    <div className="page">
      <h1>My bookings</h1>
      {flash && <div className="alert alert-ok">{flash}</div>}
      {error && <ErrorState message={error} onRetry={load} />}

      <div className="chip-row">
        {FILTERS.map((f) => (
          <button key={f} className={`chip-tag ${filter === f ? 'on' : ''}`} onClick={() => setFilter(f)}>
            {f}
          </button>
        ))}
      </div>

      {!bookings && !error && <Spinner />}
      {bookings && visible.length === 0 && (
        <EmptyState title="No bookings here" hint="Try another filter, or create a new booking.">
          <button className="btn btn-primary btn-sm" onClick={() => navigate('/customer/services')}>
            Book a service
          </button>
        </EmptyState>
      )}

      <div className="cards-grid">
        {visible.map((b) => (
          <BookingCard
            key={b.id}
            booking={b}
            perspective="customer"
            actions={actionsFor(b)}
            onAction={onAction}
            footer={
              b.status === 'COMPLETED' ? (
                <div className="booking-footer">
                  <PayNow booking={b} />
                  <ReviewWidget bookingId={b.id} />
                </div>
              ) : null
            }
          />
        ))}
      </div>
    </div>
  )
}
