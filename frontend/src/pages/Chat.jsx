import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import ChatBox from '../components/ChatBox'
import { EmptyState, Spinner } from '../components/Loading'
import { useAuth } from '../context/AuthContext'
import { apiError } from '../services/api'
import { getBooking } from '../services/bookingService'

/** Chat page for a booking. Access is server-enforced; 403 renders as a friendly note. */
export default function Chat() {
  const { bookingId } = useParams()
  const { isExpert } = useAuth()
  const navigate = useNavigate()
  const [booking, setBooking] = useState(null)
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    getBooking(bookingId)
      .then(setBooking)
      .catch((err) => setError(apiError(err)))
      .finally(() => setLoaded(true))
  }, [bookingId])

  return (
    <div className="page page-narrow">
      <button className="btn btn-outline btn-sm" onClick={() => navigate(-1)}>← Back</button>
      {!loaded && <Spinner />}
      {loaded && error && (
        <EmptyState title="Chat unavailable" hint={error}>
          <button className="btn btn-primary btn-sm" onClick={() => navigate(-1)}>Go back</button>
        </EmptyState>
      )}
      {loaded && !error && (
        <>
          {['PENDING', 'ACCEPTED', 'COMPLETED'].includes(booking?.status) ? (
            <ChatBox bookingId={Number(bookingId)} />
          ) : (
            <EmptyState
              title={`Chat is not available for ${booking?.status} bookings`}
              hint="Rejected and cancelled bookings cannot be chatted in (server rule)."
            />
          )}
          {isExpert && booking?.status === 'ACCEPTED' && (
            <p className="muted small center">
              On your way? <button className="btn btn-outline btn-sm" onClick={() => navigate(`/expert/bookings/${bookingId}/tracking`)}>Start location sharing</button>
            </p>
          )}
        </>
      )}
    </div>
  )
}
