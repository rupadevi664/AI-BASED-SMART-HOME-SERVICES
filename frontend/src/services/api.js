import axios from 'axios'

// Resilient API and WebSocket base resolution for both local dev and production
function getDefaultApiBase() {
  if (import.meta.env.VITE_API_BASE_URL) return import.meta.env.VITE_API_BASE_URL
  if (typeof window !== 'undefined' && window.location.origin && import.meta.env.PROD) {
    return window.location.origin
  }
  return 'http://127.0.0.1:8000'
}

function getDefaultWsBase() {
  if (import.meta.env.VITE_WS_BASE_URL) return import.meta.env.VITE_WS_BASE_URL
  if (typeof window !== 'undefined' && window.location.host && import.meta.env.PROD) {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}`
  }
  return 'ws://127.0.0.1:8000'
}

// REST base and WebSocket base (ws://host or wss://host)
export const API_BASE = getDefaultApiBase()
export const WS_BASE = getDefaultWsBase()

// Central Axios instance — base URL from env/origin, JWT attached automatically.
export const api = axios.create({
  baseURL: API_BASE,
})

// Attach the JWT to every request.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Extract a friendly message from the backend's varied error shapes:
// - Booking errors: { error: { code, message } }
// - Plain HTTPException: string detail
// - Validation: [{ field, message }]
export function apiError(err) {
  if (err?.response) {
    const { status, data } = err.response
    const detail = data?.detail
    if (typeof detail === 'object' && detail?.error?.message) return detail.error.message
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((e) => `${e.field || 'input'}: ${e.message || 'invalid value'}`)
        .join('; ')
    }
    if (data?.message) return data.message
    return `Request failed (${status})`
  }
  if (err?.request) return 'Cannot reach the server. Is the backend running?'
  return err?.message || 'Unexpected error'
}

// Shared 401 handling: clear the session and send the user to login.
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      const hadToken = localStorage.getItem('token')
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (hadToken && !window.location.pathname.startsWith('/login')) {
        window.location.replace('/login?expired=1')
      }
    }
    return Promise.reject(err)
  },
)


