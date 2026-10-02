import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import BookingCard from '../components/BookingCard'
import { EmptyState, ErrorState, Spinner } from '../components/Loading'
import { apiError } from '../services/api'
import { acceptBooking, completeBooking, getExpertBookings, rejectBooking } from '../services/bookingService'

const FILTERS = ['ALL', 'PENDING', 'ACCEPTED', 'COMPLETED', 'REJECTED', 'CANCELLED']

export default function ExpertBookings() {
  const navigate = useNavigate()
  const [bookings, setBookings] = useState(null)
  const [filter, setFilter] = useState('ALL')
  const [error, setError] = useState('')
  const [flash, setFlash] = useState('')
  const [busyId, setBusyId] = useState(null)

  async function load() {
    setError('')
    try {
      setBookings(await getExpertBookings())
    } catch (err) {
      setError(apiError(err))
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function onAction(key, booking) {
    if (key === 'chat') return navigate(`/expert/bookings/${booking.id}/chat`)
    if (key === 'track') return navigate(`/expert/bookings/${booking.id}/tracking`)
    setBusyId(booking.id)
    setFlash('')
    try {
      if (key === 'accept') await acceptBooking(booking.id)
      if (key === 'reject') {
        const reason = window.prompt('Rejection reason (min 3 characters):')
        if (!reason || reason.trim().length < 3) {
          setBusyId(null)
          return
        }
        await rejectBooking(booking.id, reason.trim())
      }
      if (key === 'complete') await completeBooking(booking.id)
      await load()
    } catch (err) {
      setError(apiError(err))
    } finally {
      setBusyId(null)
    }
  }

  function actionsFor(b) {
    if (b.status === 'PENDING')
      return [
        { key: 'accept', label: '✓ Accept', disabled: busyId === b.id },
        { key: 'reject', label: '✗ Reject', kind: 'btn-danger', disabled: busyId === b.id },
        { key: 'chat', label: '💬 Chat', kind: 'btn-secondary' },
      ]
    if (b.status === 'ACCEPTED')
      return [
        { key: 'complete', label: 'Mark completed', disabled: busyId === b.id },
        { key: 'chat', label: '💬 Chat', kind: 'btn-secondary' },
        { key: 'track', label: '📍 Share location', kind: 'btn-outline' },
      ]
    return [{ key: 'chat', label: '💬 Chat', kind: 'btn-secondary' }]
  }

  const visible = (bookings || []).filter((b) => filter === 'ALL' || b.status === filter)

  return (
    <div className="page">
      <h1>Booking requests</h1>
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
      {bookings && visible.length === 0 && <EmptyState title="Nothing here" hint="Try a different filter." />}

      <div className="cards-grid">
        {visible.map((b) => (
          <BookingCard key={b.id} booking={b} perspective="expert" actions={actionsFor(b)} onAction={onAction} />
        ))}
      </div>
    </div>
  )
}
