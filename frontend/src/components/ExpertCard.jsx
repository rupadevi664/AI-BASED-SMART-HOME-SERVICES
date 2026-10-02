import { AvailabilityBadge, VerifyBadge } from './Badges'

/** Fields come straight from GET /experts/nearby (NearbyExpertResponse). */
export default function ExpertCard({ expert, onViewProfile, onBook }) {
  return (
    <div className="card expert-card">
      <div className="card-head">
        <div>
          <h3>{expert.name}</h3>
          <p className="muted small">{expert.location}</p>
        </div>
        <VerifyBadge status={expert.verification_status} />
      </div>

      <div className="card-body">
        <p className="small">
          <strong>Skills:</strong> {expert.skills}
        </p>
        <p className="small">
          <strong>Experience:</strong> {expert.experience_years} yrs
        </p>
        <p className="small">
          <strong>Services:</strong>{' '}
          {expert.services?.length ? expert.services.map((s) => s.name).join(', ') : '—'}
        </p>
        <div className="card-meta">
          <AvailabilityBadge status={expert.availability} />
          <span className="distance">📍 {expert.distance_km} km away</span>
        </div>
      </div>

      <div className="card-actions">
        {onViewProfile && (
          <button className="btn btn-secondary btn-sm" onClick={() => onViewProfile(expert)}>
            View Profile
          </button>
        )}
        {onBook && (
          <button className="btn btn-primary btn-sm" onClick={() => onBook(expert)}>
            Book Now
          </button>
        )}
      </div>
    </div>
  )
}
