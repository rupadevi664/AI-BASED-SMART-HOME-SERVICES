import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import BookingCard from '../components/BookingCard'
import {
  IconArrowRight,
  IconBot,
  IconCalendar,
  IconCheckCircle,
  IconClock,
  IconSparkles,
  IconWrench,
} from '../components/Icons'
import { EmptyState, ErrorState, Spinner } from '../components/Loading'
import { useAuth } from '../context/AuthContext'
import { apiError } from '../services/api'
import { getMyBookings } from '../services/bookingService'

export default function CustomerDashboard() {
  const { user } = useAuth()
  const [bookings, setBookings] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getMyBookings()
      .then(setBookings)
      .catch((err) => setError(apiError(err)))
  }, [])

  const active = (bookings || []).filter((b) => ['PENDING', 'ACCEPTED'].includes(b.status))
  const completed = (bookings || []).filter((b) => b.status === 'COMPLETED')

  return (
    <div className="page">
      {/* Hero Welcome Banner */}
      <section className="hero-section">
        <div className="hero-content">
          <div className="hero-badge">
            <IconSparkles size={13} />
            <span>Smart Home Experience</span>
          </div>
          <h1 className="hero-title">Welcome back, {user?.name?.split(' ')[0] || 'Friend'}!</h1>
          <p className="hero-desc">
            Instantly connect with verified electricians, plumbers, and home experts with real-time GPS tracking and guaranteed fixed rates.
          </p>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <Link to="/customer/services" className="btn btn-primary">
              <IconWrench size={16} />
              <span>Book a Pro</span>
            </Link>
            <Link
              to="/customer/assistant"
              className="btn btn-outline"
              style={{ background: 'rgba(255,255,255,0.1)', color: '#fff', borderColor: 'rgba(255,255,255,0.2)' }}
            >
              <IconBot size={16} />
              <span>Ask AI Diagnostics</span>
            </Link>
          </div>
        </div>
      </section>

      {/* KPI Stats Grid */}
      <div className="stat-grid">
        <div className="stat brand">
          <div className="stat-header">
            <span className="stat-label">Active Bookings</span>
            <IconClock size={18} />
          </div>
          <span className="stat-num">{active.length}</span>
          <span className="muted tiny">In progress or pending</span>
        </div>

        <div className="stat ok">
          <div className="stat-header">
            <span className="stat-label">Completed</span>
            <IconCheckCircle size={18} />
          </div>
          <span className="stat-num">{completed.length}</span>
          <span className="muted tiny">Successfully serviced</span>
        </div>

        <div className="stat">
          <div className="stat-header">
            <span className="stat-label">Total Requests</span>
            <IconCalendar size={18} />
          </div>
          <span className="stat-num">{(bookings || []).length}</span>
          <span className="muted tiny">Lifetime orders</span>
        </div>
      </div>

      {/* Active Bookings Section */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', margin: '24px 0 12px' }}>
        <h2 style={{ margin: 0 }}>Active Bookings</h2>
        {bookings && bookings.length > 0 && (
          <Link to="/customer/bookings" className="small" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span>View all</span>
            <IconArrowRight size={13} />
          </Link>
        )}
      </div>

      {error && <ErrorState message={error} onRetry={() => setError('')} />}
      {!bookings && !error && <Spinner label="Loading your dashboard…" />}

      {bookings && active.length === 0 && (
        <EmptyState
          title="No active bookings right now"
          hint="Need something fixed? Pick a service and we'll dispatch a top-rated pro."
          icon="🛠️"
        >
          <Link to="/customer/services" className="btn btn-primary btn-sm">
            Explore Services
          </Link>
        </EmptyState>
      )}

      <div className="cards-grid">
        {active.map((b) => (
          <BookingCard key={b.id} booking={b} perspective="customer" />
        ))}
      </div>

      {/* Booking History Section */}
      {bookings && bookings.length > active.length && (
        <>
          <h2 style={{ marginTop: '36px' }}>Recent Activity</h2>
          <div className="cards-grid">
            {bookings
              .filter((b) => !['PENDING', 'ACCEPTED'].includes(b.status))
              .slice(0, 4)
              .map((b) => (
                <BookingCard key={b.id} booking={b} perspective="customer" />
              ))}
          </div>
        </>
      )}
    </div>
  )
}
