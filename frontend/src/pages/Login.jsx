import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
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
      // Honor "from" (protected-route redirect), else role home.
      const from = location.state?.from
      navigate(from && from !== '/login' ? from : ROLE_HOME[me.role] || '/', { replace: true })
    } catch (err) {
      setError(apiError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-shell">
      <form className="card auth-card" onSubmit={submit}>
        <h2>Welcome back</h2>
        <p className="muted small">Sign in to book trusted home-service experts.</p>

        {expired && <div className="alert alert-warn">Session expired — please sign in again.</div>}
        {error && <div className="alert alert-error">{error}</div>}

        <label>Email</label>
        <input
          type="email"
          required
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          placeholder="you@example.com"
          autoComplete="email"
        />

        <label>Password</label>
        <input
          type="password"
          required
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          placeholder="••••••••"
          autoComplete="current-password"
        />

        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>

        <p className="muted small center">
          New here? <Link to="/register">Create an account</Link>
        </p>
      </form>
    </div>
  )
}
