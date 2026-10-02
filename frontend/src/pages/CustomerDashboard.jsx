import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import BookingCard from '../components/BookingCard'
import { EmptyState, ErrorState, Spinner } from '../components/Loading'
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

  return (
    <div className="page">
      <h1>Welcome, {user?.name?.split(' ')[0]} 👋</h1>
      <p className="muted">Book trusted home-service experts and follow them in real time.</p>

      <div className="quick-actions">
        <Link to="/customer/services" className="btn btn-primary">🛠️ Book a service</Link>
        <Link to="/customer/bookings" className="btn btn-outline">📋 My bookings</Link>
      </div>

      <h2>Active bookings</h2>
      {error && <ErrorState message={error} onRetry={() => setError('')} />}
      {!bookings && !error && <Spinner />}
      {bookings && active.length === 0 && (
        <EmptyState title="No active bookings" hint="Pick a service to find verified experts near you.">
          <Link to="/customer/services" className="btn btn-primary btn-sm">Browse services</Link>
        </EmptyState>
      )}
      <div className="cards-grid">
        {active.map((b) => (
          <BookingCard key={b.id} booking={b} perspective="customer" />
        ))}
      </div>

      {bookings && bookings.length > active.length && (
        <>
          <h2>History</h2>
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
