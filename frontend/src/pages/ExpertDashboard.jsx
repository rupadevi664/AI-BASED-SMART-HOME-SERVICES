import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import BookingCard from '../components/BookingCard'
import { AvailabilityBadge, VerifyBadge } from '../components/Badges'
import { EmptyState, ErrorState, Spinner } from '../components/Loading'
import { useAuth } from '../context/AuthContext'
import { apiError } from '../services/api'
import { acceptBooking, completeBooking, getExpertBookings, rejectBooking } from '../services/bookingService'

export default function ExpertDashboard() {
  const { expertProfile, user, refreshUser } = useAuth()
  const navigate = useNavigate()
  const [bookings, setBookings] = useState(null)
  const [error, setError] = useState('')
  const [flash, setFlash] = useState('')
  const [busyId, setBusyId] = useState(null)

  async function load() {
    try {
      setBookings(await getExpertBookings())
    } catch (err) {
      setError(apiError(err))
    }
  }

  useEffect(() => {
    load()
  }, [])

  const pending = (bookings || []).filter((b) => b.status === 'PENDING')
  const accepted = (bookings || []).filter((b) => b.status === 'ACCEPTED')
  const done = (bookings || []).filter((b) => ['COMPLETED', 'REJECTED', 'CANCELLED'].includes(b.status))

  async function onAction(key, booking) {
    if (key === 'chat') return navigate(`/expert/bookings/${booking.id}/chat`)
    if (key === 'track') return navigate(`/expert/bookings/${booking.id}/tracking`)
    setBusyId(booking.id)
    setFlash('')
    try {
      if (key === 'accept') {
        await acceptBooking(booking.id)
        setFlash(`Booking #${booking.id} accepted — chat is open and you can share location once on site.`)
      } else if (key === 'reject') {
        const reason = window.prompt('Rejection reason (min 3 characters):')
        if (!reason || reason.trim().length < 3) {
          setBusyId(null)
          return
        }
        await rejectBooking(booking.id, reason.trim())
        setFlash(`Booking #${booking.id} rejected.`)
      } else if (key === 'complete') {
        await completeBooking(booking.id)
        setFlash(`Booking #${booking.id} marked completed. 🎉`)
      }
      await load()
      refreshUser()
    } catch (err) {
      setError(apiError(err))
    } finally {
      setBusyId(null)
    }
  }

  function actionsFor(b) {
    if (b.status === 'PENDING') {
      return [
        { key: 'accept', label: '✓ Accept', disabled: busyId === b.id },
        { key: 'reject', label: '✗ Reject', kind: 'btn-danger', disabled: busyId === b.id },
        { key: 'chat', label: '💬 Chat', kind: 'btn-secondary' },
      ]
    }
    if (b.status === 'ACCEPTED') {
      return [
        { key: 'complete', label: 'Mark completed', disabled: busyId === b.id },
        { key: 'chat', label: '💬 Chat', kind: 'btn-secondary' },
        { key: 'track', label: '📍 Share location', kind: 'btn-outline' },
      ]
    }
    return [{ key: 'chat', label: '💬 Chat', kind: 'btn-secondary' }]
  }

  const unverified = expertProfile?.verification_status !== 'VERIFIED'

  return (
    <div className="page">
      <h1>Expert dashboard</h1>
      <p className="muted small">
        {user?.name} · Profile #{expertProfile?.id} <VerifyBadge status={expertProfile?.verification_status} />{' '}
        <AvailabilityBadge status={expertProfile?.availability} />
      </p>

      {unverified && (
        <div className="alert alert-warn">
          Your profile is <strong>{expertProfile?.verification_status || 'PENDING'}</strong>. An admin must verify
          you before customers can book you.
        </div>
      )}
      {expertProfile?.availability === 'UNAVAILABLE' && (
        <div className="alert alert-warn">
          You are currently <strong>UNAVAILABLE</strong> — accept is blocked until you switch availability in
          <Link to="/expert/profile"> My Profile</Link>.
        </div>
      )}
      {flash && <div className="alert alert-ok">{flash}</div>}
      {error && <ErrorState message={error} onRetry={load} />}

      {!bookings && !error && <Spinner />}

      <h2>Incoming requests ({pending.length})</h2>
      {bookings && pending.length === 0 && <EmptyState title="No pending requests" hint="New requests appear here instantly after you reload." />}
      <div className="cards-grid">
        {pending.map((b) => (
          <BookingCard key={b.id} booking={b} perspective="expert" actions={actionsFor(b)} onAction={onAction} />
        ))}
      </div>

      <h2>Active jobs ({accepted.length})</h2>
      {bookings && accepted.length === 0 && <EmptyState title="No active jobs" hint="Accepted bookings show up here." />}
      <div className="cards-grid">
        {accepted.map((b) => (
          <BookingCard key={b.id} booking={b} perspective="expert" actions={actionsFor(b)} onAction={onAction} />
        ))}
      </div>

      {done.length > 0 && (
        <>
          <h2>Past</h2>
          <div className="cards-grid">
            {done.slice(0, 4).map((b) => (
              <BookingCard key={b.id} booking={b} perspective="expert" actions={actionsFor(b)} onAction={onAction} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
