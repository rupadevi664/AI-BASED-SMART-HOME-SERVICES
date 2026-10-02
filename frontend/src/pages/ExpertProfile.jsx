import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { AvailabilityBadge, VerifyBadge } from '../components/Badges'
import { EmptyState } from '../components/Loading'
import { getExpertReviews } from '../services/reviewService'

/** Star row for a 1-5 rating (handles halves by flooring). */
function Stars({ value }) {
  if (value == null) return <span className="muted small">No ratings yet</span>
  const full = Math.round(value)
  return (
    <span className="stars" aria-label={`${value.toFixed(1)} out of 5`}>
      {'★'.repeat(full)}
      <span className="stars-off">{'★'.repeat(5 - full)}</span>
    </span>
  )
}

/**
 * Expert profile. The backend has no public GET /experts/{id}, so this page
 * renders the NearbyExpertResponse row passed via router state, and pulls
 * reviews + the average rating from the public /reviews/expert/{id} endpoint.
 */
export default function ExpertProfile() {
  const { state } = useLocation()
  const navigate = useNavigate()
  const expert = state?.expert
  const [reviews, setReviews] = useState(null)

  useEffect(() => {
    if (!expert?.expert_id) return
    let alive = true
    getExpertReviews(expert.expert_id)
      .then((r) => alive && setReviews(r))
      .catch(() => alive && setReviews({ average_rating: null, total_reviews: 0, reviews: [] }))
    return () => {
      alive = false
    }
  }, [expert?.expert_id])

  if (!expert) {
    return (
      <div className="page">
        <EmptyState title="Expert not found" hint="Open an expert profile from the nearby-experts search.">
          <button className="btn btn-primary btn-sm" onClick={() => navigate('/customer/experts')}>
            Find experts
          </button>
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="page">
      <button className="btn btn-outline btn-sm" onClick={() => navigate(-1)}>
        ← Back
      </button>

      <div className="card profile-card">
        <div className="card-head">
          <div>
            <h1>{expert.name}</h1>
            <p className="muted small">Expert #{expert.expert_id} · {expert.location}</p>
          </div>
          <VerifyBadge status={expert.verification_status} />
        </div>

        <div className="rating-line">
          <Stars value={reviews?.average_rating ?? expert.rating_avg} />
          <span className="strong">
            {reviews?.average_rating != null ? reviews.average_rating.toFixed(1) : '—'}
          </span>
          <span className="muted small">
            {reviews ? `${reviews.total_reviews} review${reviews.total_reviews === 1 ? '' : 's'}` : 'Loading reviews…'}
          </span>
        </div>

        <div className="profile-grid">
          <div>
            <h4>Skills</h4>
            <p>{expert.skills}</p>
            <h4>Services offered</h4>
            <p>{expert.services?.length ? expert.services.map((s) => s.name).join(', ') : '—'}</p>
          </div>
          <div>
            <h4>Experience</h4>
            <p>{expert.experience_years} years</p>
            <h4>Availability</h4>
            <p><AvailabilityBadge status={expert.availability} /></p>
            <h4>Distance</h4>
            <p>📍 {expert.distance_km} km from your search point</p>
          </div>
        </div>

        <button
          className="btn btn-primary btn-block"
          onClick={() =>
            navigate('/customer/book/new', {
              state: { expert: { expert_id: expert.expert_id, name: expert.name, services: expert.services, location: expert.location } },
            })
          }
        >
          Book {expert.name}
        </button>

        {reviews && reviews.reviews.length > 0 && (
          <div className="reviews-section">
            <h4>Customer reviews</h4>
            {reviews.reviews.map((r) => (
              <div key={r.id} className="review-item">
                <div className="review-item-head">
                  <Stars value={r.rating} />
                  <span className="strong small">{r.customer?.name || `Customer #${r.customer_id}`}</span>
                  <span className="muted small">
                    {new Date(r.created_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}
                  </span>
                </div>
                {r.comment && <p className="small">“{r.comment}”</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
