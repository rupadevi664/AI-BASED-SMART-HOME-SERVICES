import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { IconAlert, IconArrowRight, IconHome, IconMail, IconSparkles } from '../components/Icons'
import { useAuth } from '../context/AuthContext'
import { apiError } from '../services/api'
import { getMe, login as loginApi } from '../services/authService'

const ROLE_HOME = {
  ADMIN: '/admin/dashboard',
  EXPERT: '/expert/dashboard',
  CUSTOMER: '/customer/dashboard',
}

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Arriving here after a 401 elsewhere.
  const expired = new URLSearchParams(location.search).get('expired')

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const { access_token } = await loginApi(form.email.trim(), form.password)
      const me = await getMe(access_token)
      login(access_token, me)
      const from = location.state?.from
      navigate(from && from !== '/login' ? from : ROLE_HOME[me.role] || '/', { replace: true })
    } catch (err) {
      setError(apiError(err))
    } finally {
      setBusy(false)
    }
  }

  function fillDemo(email, password) {
    setForm({ email, password })
  }

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={submit}>
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              background: 'var(--brand-gradient)',
              borderRadius: '14px',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              marginBottom: '12px',
              boxShadow: 'var(--shadow-primary)',
            }}
          >
            <IconHome size={24} />
          </div>
          <h2 style={{ fontSize: '24px', margin: '0 0 4px' }}>Welcome back</h2>
          <p className="muted small" style={{ margin: 0 }}>
            Sign in to access your bookings and smart home services.
          </p>
        </div>

        {expired && <div className="alert alert-warn">Session expired — please sign in again.</div>}
        {error && (
          <div className="alert alert-error">
            <IconAlert size={16} />
            <span>{error}</span>
          </div>
        )}

        <label>Email Address</label>
        <input
          type="email"
          required
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          placeholder="name@example.com"
          autoComplete="email"
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '14px' }}>
          <label style={{ margin: 0 }}>Password</label>
        </div>
        <input
          type="password"
          required
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          placeholder="••••••••"
          autoComplete="current-password"
          style={{ marginTop: '6px' }}
        />

        <button className="btn btn-primary btn-block btn-lg" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign In'}
          {!busy && <IconArrowRight size={16} />}
        </button>

        {/* Demo login pills */}
        <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px dashed var(--line)' }}>
          <span className="muted tiny" style={{ display: 'block', textAlign: 'center', marginBottom: '8px' }}>
            Quick fill demo accounts:
          </span>
          <div style={{ display: 'flex', gap: '6px', justifyContent: 'center' }}>
            <button
              type="button"
              className="chip-tag tiny"
              onClick={() => fillDemo('admin123@example.com', 'Rupa@123')}
            >
              Admin
            </button>
          </div>
        </div>

        <p className="muted small center" style={{ marginTop: '20px' }}>
          Don't have an account?{' '}
          <Link to="/register" style={{ fontWeight: 600 }}>
            Create one now
          </Link>
        </p>
      </form>
    </div>
  )
}
