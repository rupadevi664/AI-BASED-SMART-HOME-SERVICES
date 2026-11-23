import { useEffect, useState } from 'react'
import { AvailabilityBadge, StatusBadge, VerifyBadge } from '../components/Badges'
import {
  IconBriefcase,
  IconCalendar,
  IconCheck,
  IconCheckCircle,
  IconClock,
  IconShieldCheck,
  IconSparkles,
  IconUser,
  IconWrench,
  IconX,
} from '../components/Icons'
import { EmptyState, ErrorState, Spinner } from '../components/Loading'
import { api, apiError } from '../services/api'
import { adminListBookings } from '../services/bookingService'
import { adminListExperts, adminSetVerification } from '../services/expertService'
import { createService, listServices, updateService } from '../services/serviceService'

// GET /admin/dashboard (ADMIN only)
async function getDashboard() {
  const { data } = await api.get('/admin/dashboard')
  return data
}

export default function AdminDashboard() {
  const [stats, setStats] = useState(null)
  const [experts, setExperts] = useState(null)
  const [services, setServices] = useState(null)
  const [bookings, setBookings] = useState(null)
  const [error, setError] = useState('')
  const [flash, setFlash] = useState('')
  const [tab, setTab] = useState('experts')
  const [svcForm, setSvcForm] = useState({ name: '', description: '', base_price: '' })

  async function loadAll() {
    setError('')
    try {
      const [dash, ex, sv, bk] = await Promise.all([
        getDashboard(),
        adminListExperts(),
        listServices(),
        adminListBookings(),
      ])
      setStats(dash.stats)
      setExperts(ex)
      setServices(sv)
      setBookings(bk)
    } catch (err) {
      setError(apiError(err))
    }
  }

  useEffect(() => {
    loadAll()
  }, [])

  async function verify(expertId, status) {
    setFlash('')
    try {
      await adminSetVerification(expertId, status)
      setFlash(`Expert #${expertId} verification updated to: ${status}`)
      loadAll()
    } catch (err) {
      setError(apiError(err))
    }
  }

  async function addService(e) {
    e.preventDefault()
    setFlash('')
    try {
      await createService({
        name: svcForm.name.trim(),
        description: svcForm.description.trim(),
        base_price: Number(svcForm.base_price),
      })
      setSvcForm({ name: '', description: '', base_price: '' })
      setFlash('New service added successfully.')
      loadAll()
    } catch (err) {
      setError(apiError(err))
    }
  }

  async function toggleServiceStatus(s) {
    setFlash('')
    try {
      await updateService(s.id, { status: s.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE' })
      setFlash(`${s.name} is now ${s.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'}`)
      loadAll()
    } catch (err) {
      setError(apiError(err))
    }
  }

  return (
    <div className="page">
      <div style={{ marginBottom: '20px' }}>
        <h1 style={{ margin: '0 0 4px' }}>Platform Administration</h1>
        <p className="muted" style={{ margin: 0 }}>
          Manage provider verifications, catalog offerings, and platform metrics.
        </p>
      </div>

      {flash && <div className="alert alert-ok">{flash}</div>}
      {error && <ErrorState message={error} onRetry={loadAll} />}
      {!stats && !error && <Spinner label="Loading administrative statistics…" />}

      {stats && (
        <>
          {/* KPI Stat Cards */}
          <div className="stat-grid">
            <div className="stat">
              <div className="stat-header">
                <span className="stat-label">Total Users</span>
                <IconUser size={18} />
              </div>
              <span className="stat-num">{stats.total_users}</span>
              <span className="muted tiny">Platform registered accounts</span>
            </div>

            <div className="stat brand">
              <div className="stat-header">
                <span className="stat-label">Verified Experts</span>
                <IconShieldCheck size={18} />
              </div>
              <span className="stat-num">{stats.total_experts}</span>
              <span className="muted tiny">Active service providers</span>
            </div>

            <div className="stat">
              <div className="stat-header">
                <span className="stat-label">Services</span>
                <IconWrench size={18} />
              </div>
              <span className="stat-num">{stats.total_services}</span>
              <span className="muted tiny">Active catalog categories</span>
            </div>

            <div className="stat warn">
              <div className="stat-header">
                <span className="stat-label">Pending Verification</span>
                <IconClock size={18} />
              </div>
              <span className="stat-num">{stats.pending_verifications}</span>
              <span className="muted tiny">Awaiting background check</span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="chip-row">
            {[
              { id: 'experts', label: 'Experts & Verification', count: experts?.length },
              { id: 'services', label: 'Service Catalogue', count: services?.length },
              { id: 'bookings', label: 'All Bookings', count: bookings?.length },
            ].map((t) => (
              <button
                key={t.id}
                className={`chip-tag ${tab === t.id ? 'on' : ''}`}
                onClick={() => setTab(t.id)}
              >
                {t.label} ({t.count ?? 0})
              </button>
            ))}
          </div>

          {tab === 'experts' && (
            <>
              {experts && experts.length === 0 && <EmptyState title="No experts registered yet" />}
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Expert Name</th>
                      <th>Skills</th>
                      <th>Experience</th>
                      <th>Availability</th>
                      <th>Verification</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(experts || []).map((e) => (
                      <tr key={e.id}>
                        <td>
                          <strong>{e.name}</strong>
                          <br />
                          <span className="muted tiny">{e.email}</span>
                        </td>
                        <td className="small">{e.skills}</td>
                        <td>{e.experience_years} yrs</td>
                        <td><AvailabilityBadge status={e.availability} /></td>
                        <td><VerifyBadge status={e.verification_status} /></td>
                        <td>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            {e.verification_status !== 'VERIFIED' && (
                              <button
                                className="btn btn-sm btn-primary"
                                onClick={() => verify(e.id, 'VERIFIED')}
                              >
                                <IconCheck size={13} />
                                <span>Verify</span>
                              </button>
                            )}
                            {e.verification_status !== 'REJECTED' && (
                              <button
                                className="btn btn-sm btn-danger"
                                onClick={() => verify(e.id, 'REJECTED')}
                              >
                                <IconX size={13} />
                                <span>Reject</span>
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {tab === 'services' && (
            <>
              <form className="card form-card" onSubmit={addService} style={{ marginBottom: '20px' }}>
                <h3 style={{ margin: '0 0 12px' }}>Add New Service Category</h3>
                <div className="filter-row">
                  <div style={{ flex: 1, minWidth: '150px' }}>
                    <label style={{ margin: '0 0 4px' }}>Name</label>
                    <input
                      required
                      minLength={2}
                      placeholder="e.g. Solar Panel Cleaning"
                      value={svcForm.name}
                      onChange={(e) => setSvcForm({ ...svcForm, name: e.target.value })}
                    />
                  </div>
                  <div style={{ width: '130px' }}>
                    <label style={{ margin: '0 0 4px' }}>Base Price ₹</label>
                    <input
                      required
                      type="number"
                      min={1}
                      step="0.01"
                      placeholder="499"
                      value={svcForm.base_price}
                      onChange={(e) => setSvcForm({ ...svcForm, base_price: e.target.value })}
                    />
                  </div>
                  <div style={{ flex: 2, minWidth: '200px' }}>
                    <label style={{ margin: '0 0 4px' }}>Description</label>
                    <input
                      placeholder="Short scope of work description"
                      value={svcForm.description}
                      onChange={(e) => setSvcForm({ ...svcForm, description: e.target.value })}
                    />
                  </div>
                  <div>
                    <label style={{ margin: '0 0 4px' }}>&nbsp;</label>
                    <button className="btn btn-primary">
                      <span>Add Service</span>
                    </button>
                  </div>
                </div>
              </form>

              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Service Name</th>
                      <th>Base Rate</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(services || []).map((s) => (
                      <tr key={s.id}>
                        <td>
                          <strong>{s.name}</strong>
                          <br />
                          <span className="muted tiny clamp">{s.description}</span>
                        </td>
                        <td className="strong">₹{Number(s.base_price).toFixed(2)}</td>
                        <td>
                          <span className={`badge ${s.status === 'ACTIVE' ? 'badge-accepted' : 'badge-cancelled'}`}>
                            {s.status}
                          </span>
                        </td>
                        <td>
                          <button
                            className="btn btn-sm btn-outline"
                            onClick={() => toggleServiceStatus(s)}
                          >
                            {s.status === 'ACTIVE' ? 'Deactivate' : 'Activate'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {tab === 'bookings' && (
            <>
              {bookings && bookings.length === 0 && <EmptyState title="No bookings recorded yet" />}
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Service</th>
                      <th>Customer ID</th>
                      <th>Expert ID</th>
                      <th>Scheduled Date</th>
                      <th>Amount</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(bookings || []).map((b) => (
                      <tr key={b.id}>
                        <td className="mono small">#{b.id}</td>
                        <td><strong>{b.service_name}</strong></td>
                        <td className="mono small">User #{b.customer_id}</td>
                        <td className="mono small">Expert #{b.expert_id}</td>
                        <td className="small">{b.scheduled_date} {b.scheduled_time?.slice(0, 5)}</td>
                        <td className="strong">₹{Number(b.service_price).toFixed(2)}</td>
                        <td><StatusBadge status={b.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
