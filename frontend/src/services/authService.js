import { api } from './api'

// POST /auth/login  { email, password } → { access_token, token_type }
export async function login(email, password) {
  const { data } = await api.post('/auth/login', { email, password })
  return data // { access_token, token_type }
}

// POST /auth/register → UserResponse (role forced to CUSTOMER server-side)
export async function registerCustomer({ name, email, phone, password }) {
  const { data } = await api.post('/auth/register', { name, email, phone, password })
  return data
}

// POST /auth/register-expert → { user, expert_profile }
export async function registerExpert(payload) {
  const { data } = await api.post('/auth/register-expert', payload)
  return data
}

// GET /auth/me → { id, name, email, phone, role, is_active, expert_profile? }
// `token` is optional — pass it right after login BEFORE it lands in storage.
export async function getMe(token = null) {
  const config = token ? { headers: { Authorization: `Bearer ${token}` } } : undefined
  const { data } = await api.get('/auth/me', config)
  return data
}

export const TOKEN_KEY = 'token'
export const USER_KEY = 'user'
