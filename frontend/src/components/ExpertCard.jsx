import { AvailabilityBadge, VerifyBadge } from './Badges'
import {
  IconArrowRight,
  IconBriefcase,
  IconCalendar,
  IconMapPin,
  IconStar,
  IconUser,
  IconWrench,
} from './Icons'

/** Fields come straight from GET /experts/nearby (NearbyExpertResponse). */
export default function ExpertCard({ expert, onViewProfile, onBook }) {
  const initials = expert.name
    ? expert.name
        .split(' ')
        .map((n) => n[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'EX'

  return (
    <div className="card expert-card">
      <div className="card-head">
        <div className="expert-header">
          <div className="expert-avatar">{initials}</div>
          <div>
            <h3 style={{ margin: 0, fontSize: '17px' }}>{expert.name}</h3>
            <p className="muted small" style={{ margin: '2px 0 0', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <IconMapPin size={13} />
              <span>{expert.location}</span>
            </p>
          </div>
        </div>
        <VerifyBadge status={expert.verification_status} />
      </div>

      <div className="card-body">
        <p className="small" style={{ margin: '8px 0 4px' }}>
          <IconWrench size={14} className="muted" />
          <span>
            <strong>Skills:</strong> {expert.skills}
          </span>
        </p>
        <p className="small" style={{ margin: '4px 0' }}>
          <IconBriefcase size={14} className="muted" />
          <span>
            <strong>Experience:</strong> {expert.experience_years} years
          </span>
        </p>

        {expert.services?.length ? (
          <div style={{ margin: '8px 0' }}>
            <span className="muted tiny" style={{ display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Offered Services
            </span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
              {expert.services.map((s) => (
                <span
                  key={s.id || s.name}
                  className="badge"
                  style={{ background: 'var(--brand-light)', color: 'var(--brand)', fontSize: '11px' }}
                >
                  {s.name}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        <div className="card-meta">
          <AvailabilityBadge status={expert.availability} />
          <span className="distance">
            <IconMapPin size={12} />
            {expert.distance_km} km away
          </span>
        </div>
      </div>

      <div className="card-actions">
        {onViewProfile && (
          <button className="btn btn-outline btn-sm" onClick={() => onViewProfile(expert)}>
            <IconUser size={14} />
            <span>Profile</span>
          </button>
        )}
        {onBook && (
          <button className="btn btn-primary btn-sm" onClick={() => onBook(expert)} style={{ marginLeft: 'auto' }}>
            <span>Book Expert</span>
            <IconArrowRight size={14} />
          </button>
        )}
      </div>
    </div>
  )
}
