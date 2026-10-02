import { useEffect, useState } from 'react'
import { AvailabilityBadge, StatusBadge, VerifyBadge } from '../components/Badges'
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
      setFlash(`Expert #${expertId} → ${status}`)
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
      setFlash('Service created.')
      loadAll()
    } catch (err) {
      setError(apiError(err))
    }
  }

  async function toggleServiceStatus(s) {
    setFlash('')
    try {
      await updateService(s.id, { status: s.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE' })
      setFlash(`${s.name} → ${s.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'}`)
      loadAll()
    } catch (err) {
      setError(apiError(err))
    }
  }

  return (
    <div className="page">
      <h1>Admin dashboard</h1>
      {flash && <div className="alert alert-ok">{flash}</div>}
      {error && <ErrorState message={error} onRetry={loadAll} />}
      {!stats && !error && <Spinner />}

      {stats && (
        <>
          <div className="stat-grid">
            <div className="card stat"><span className="stat-num">{stats.total_users}</span><span className="muted small">Users</span></div>
            <div className="card stat"><span className="stat-num">{stats.total_customers}</span><span className="muted small">Customers</span></div>
            <div className="card stat"><span className="stat-num">{stats.total_experts}</span><span className="muted small">Experts</span></div>
            <div className="card stat"><span className="stat-num">{stats.total_services}</span><span className="muted small">Services</span></div>
            <div className="card stat warn"><span className="stat-num">{stats.pending_verifications}</span><span className="muted small">Pending verifications</span></div>
          </div>

          <div className="chip-row">
            {['experts', 'services', 'bookings'].map((t) => (
              <button key={t} className={`chip-tag ${tab === t ? 'on' : ''}`} onClick={() => setTab(t)}>
                {t.toUpperCase()}
              </button>
            ))}
          </div>

          {tab === 'experts' && (
            <>
              {experts && experts.length === 0 && <EmptyState title="No experts registered yet" />}
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr><th>Expert</th><th>Skills</th><th>Exp</th><th>Status</th><th>Verification</th><th>Actions</th></tr>
                  </thead>
                  <tbody>
                    {(experts || []).map((e) => (
                      <tr key={e.id}>
                        <td>{e.name}<br /><span className="muted tiny">{e.email}</span></td>
                        <td className="small">{e.skills}</td>
                        <td>{e.experience_years}y</td>
                        <td><AvailabilityBadge status={e.availability} /></td>
                        <td><VerifyBadge status={e.verification_status} /></td>
                        <td>
                          {e.verification_status !== 'VERIFIED' && (
                            <button className="btn btn-sm btn-primary" onClick={() => verify(e.id, 'VERIFIED')}>Verify</button>
                          )}{' '}
                          {e.verification_status !== 'REJECTED' && (
                            <button className="btn btn-sm btn-danger" onClick={() => verify(e.id, 'REJECTED')}>Reject</button>
                          )}
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
              <form className="card form-card" onSubmit={addService}>
                <div className="filter-row">
                  <input required minLength={2} placeholder="Service name" value={svcForm.name} onChange={(e) => setSvcForm({ ...svcForm, name: e.target.value })} />
                  <input required type="number" min={1} step="0.01" placeholder="Base price ₹" value={svcForm.base_price} onChange={(e) => setSvcForm({ ...svcForm, base_price: e.target.value })} />
                  <input placeholder="Description" value={svcForm.description} onChange={(e) => setSvcForm({ ...svcForm, description: e.target.value })} />
                  <button className="btn btn-primary">Add service</button>
                </div>
              </form>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Service</th><th>Price</th><th>Status</th><th>Action</th></tr></thead>
                  <tbody>
                    {(services || []).map((s) => (
                      <tr key={s.id}>
                        <td>{s.name}<br /><span className="muted tiny clamp">{s.description}</span></td>
                        <td>₹{Number(s.base_price).toFixed(2)}</td>
                        <td><span className={`badge ${s.status === 'ACTIVE' ? 'badge-accepted' : 'badge-cancelled'}`}>{s.status}</span></td>
                        <td>
                          <button className="btn btn-sm btn-outline" onClick={() => toggleServiceStatus(s)}>
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
              {bookings && bookings.length === 0 && <EmptyState title="No bookings yet" />}
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>#</th><th>Service</th><th>Customer</th><th>Expert</th><th>When</th><th>Status</th></tr></thead>
                  <tbody>
                    {(bookings || []).slice(0, 50).map((b) => (
                      <tr key={b.id}>
                        <td>{b.id}</td>
                        <td>{b.service_name}</td>
                        <td>#{b.customer_id}</td>
                        <td>#{b.expert_id}</td>
                        <td className="small">{b.scheduled_date} {b.scheduled_time?.slice(0, 5)}</td>
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
