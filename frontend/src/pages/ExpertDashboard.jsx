import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AvailabilityBadge, VerifyBadge } from '../components/Badges'
import BookingCard from '../components/BookingCard'
import {
  IconAlert,
  IconBriefcase,
  IconCalendar,
  IconCheckCircle,
  IconClock,
  IconSparkles,
  IconUser,
} from '../components/Icons'
import { EmptyState, ErrorState, Spinner } from '../components/Loading'
import { useAuth } from '../context/AuthContext'
import { apiError } from '../services/api'
import {
  acceptBooking,
  completeBooking,
  getExpertBookings,
  rejectBooking,
} from '../services/bookingService'

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
        setFlash(`Booking #${booking.id} accepted. Chat and live GPS sharing are now available.`)
      } else if (key === 'reject') {
        const reason = window.prompt('Rejection reason (minimum 3 characters):')
        if (!reason || reason.trim().length < 3) {
          setBusyId(null)
          return
        }
        await rejectBooking(booking.id, reason.trim())
        setFlash(`Booking #${booking.id} rejected.`)
      } else if (key === 'complete') {
        await completeBooking(booking.id)
        setFlash(`Booking #${booking.id} marked as completed! Customer can now rate and pay.`)
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
        { key: 'accept', label: '✓ Accept Job', disabled: busyId === b.id },
        { key: 'reject', label: '✗ Reject', kind: 'btn-danger', disabled: busyId === b.id },
        { key: 'chat', label: '💬 Chat', kind: 'btn-secondary' },
      ]
    }
    if (b.status === 'ACCEPTED') {
      return [
        { key: 'complete', label: '✓ Mark Completed', disabled: busyId === b.id },
        { key: 'track', label: '📍 Share Location', kind: 'btn-outline' },
        { key: 'chat', label: '💬 Chat', kind: 'btn-secondary' },
      ]
    }
    return [{ key: 'chat', label: '💬 Chat', kind: 'btn-secondary' }]
  }

  const unverified = expertProfile?.verification_status !== 'VERIFIED'

  return (
    <div className="page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px', marginBottom: '20px' }}>
        <div>
          <h1 style={{ margin: '0 0 4px' }}>Expert Dashboard</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span className="muted small">Welcome, {user?.name}</span>
            <VerifyBadge status={expertProfile?.verification_status} />
            <AvailabilityBadge status={expertProfile?.availability} />
          </div>
        </div>

        <Link to="/expert/profile" className="btn btn-outline btn-sm">
          <IconUser size={14} />
          <span>Edit Profile & Services</span>
        </Link>
      </div>

      {unverified && (
        <div className="alert alert-warn">
          <IconAlert size={16} />
          <span>
            Your expert profile status is <strong>{expertProfile?.verification_status || 'PENDING'}</strong>. A platform admin must verify your profile before customer bookings go live.
          </span>
        </div>
      )}

      {expertProfile?.availability === 'UNAVAILABLE' && (
        <div className="alert alert-warn">
          <IconAlert size={16} />
          <span>
            You are currently set to <strong>UNAVAILABLE</strong>. You cannot accept new bookings until you toggle to available in{' '}
            <Link to="/expert/profile" style={{ textDecoration: 'underline' }}>My Profile</Link>.
          </span>
        </div>
      )}

      {flash && <div className="alert alert-ok">{flash}</div>}
      {error && <ErrorState message={error} onRetry={load} />}

      {/* KPI Stats */}
      <div className="stat-grid">
        <div className="stat warn">
          <div className="stat-header">
            <span className="stat-label">Pending Requests</span>
            <IconClock size={18} />
          </div>
          <span className="stat-num">{pending.length}</span>
          <span className="muted tiny">Awaiting your response</span>
        </div>

        <div className="stat brand">
          <div className="stat-header">
            <span className="stat-label">Active Jobs</span>
            <IconBriefcase size={18} />
          </div>
          <span className="stat-num">{accepted.length}</span>
          <span className="muted tiny">In progress on site</span>
        </div>

        <div className="stat ok">
          <div className="stat-header">
            <span className="stat-label">Completed Jobs</span>
            <IconCheckCircle size={18} />
          </div>
          <span className="stat-num">{done.filter((b) => b.status === 'COMPLETED').length}</span>
          <span className="muted tiny">Fulfilled services</span>
        </div>
      </div>

      {!bookings && !error && <Spinner label="Loading expert requests…" />}

      <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span>Incoming Requests</span>
        <span className="badge badge-pending" style={{ fontSize: '11px' }}>{pending.length}</span>
      </h2>
      {bookings && pending.length === 0 && (
        <EmptyState title="No pending job requests" hint="New customer bookings will appear here instantly." icon="📥" />
      )}
      <div className="cards-grid">
        {pending.map((b) => (
          <BookingCard key={b.id} booking={b} perspective="expert" actions={actionsFor(b)} onAction={onAction} />
        ))}
      </div>

      <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '36px' }}>
        <span>Active Jobs</span>
        <span className="badge badge-accepted" style={{ fontSize: '11px' }}>{accepted.length}</span>
      </h2>
      {bookings && accepted.length === 0 && (
        <EmptyState title="No active jobs right now" hint="Accept an incoming request above to begin work." icon="⚡" />
      )}
      <div className="cards-grid">
        {accepted.map((b) => (
          <BookingCard key={b.id} booking={b} perspective="expert" actions={actionsFor(b)} onAction={onAction} />
        ))}
      </div>

      {done.length > 0 && (
        <>
          <h2 style={{ marginTop: '36px' }}>Past Job History</h2>
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
