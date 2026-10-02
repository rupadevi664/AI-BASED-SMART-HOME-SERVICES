import { api } from './api'
import { WS_BASE } from './api'

// POST /bookings  (CUSTOMER only; customer_id comes from the JWT)
// Body must match BookingCreate exactly.
export async function createBooking({
  expert_id,
  service_id,
  service_address,
  service_latitude = null,
  service_longitude = null,
  scheduled_date, // "YYYY-MM-DD"
  scheduled_time, // "HH:MM:SS"
  customer_notes = null,
}) {
  const { data } = await api.post('/bookings', {
    expert_id,
    service_id,
    service_address,
    service_latitude,
    service_longitude,
    scheduled_date,
    scheduled_time,
    customer_notes,
  })
  return data
}

// GET /bookings/my?status= (CUSTOMER only)
export async function getMyBookings(status = null) {
  const params = status ? { status } : {}
  const { data } = await api.get('/bookings/my', { params })
  return data
}

// GET /bookings/{id} — owner customer, assigned expert, or ADMIN
export async function getBooking(id) {
  const { data } = await api.get(`/bookings/${id}`)
  return data
}

// PUT /bookings/{id}/cancel  { reason } (owner CUSTOMER; PENDING/ACCEPTED only)
export async function cancelBooking(id, reason) {
  const { data } = await api.put(`/bookings/${id}/cancel`, { reason })
  return data
}

// --- Expert-side booking management --------------------------------------

// GET /experts/bookings?status= (EXPERT only)
export async function getExpertBookings(status = null) {
  const params = status ? { status } : {}
  const { data } = await api.get('/experts/bookings', { params })
  return data
}

// PUT /experts/bookings/{id}/accept
export async function acceptBooking(id) {
  const { data } = await api.put(`/experts/bookings/${id}/accept`)
  return data
}

// PUT /experts/bookings/{id}/reject  { reason }
export async function rejectBooking(id, reason) {
  const { data } = await api.put(`/experts/bookings/${id}/reject`, { reason })
  return data
}

// PUT /experts/bookings/{id}/complete
export async function completeBooking(id) {
  const { data } = await api.put(`/experts/bookings/${id}/complete`)
  return data
}

// GET /admin/bookings (ADMIN only; optional filters)
export async function adminListBookings(filters = {}) {
  const params = {}
  for (const key of ['status', 'service_id', 'expert_id', 'customer_id']) {
    if (filters[key] != null && filters[key] !== '') params[key] = filters[key]
  }
  const { data } = await api.get('/admin/bookings', { params })
  return data
}

// --- REST location (Phase 5) ----------------------------------------------

// GET /bookings/{id}/location → latest fix (404 NO_LOCATION_AVAILABLE if none)
export async function getLatestLocation(bookingId) {
  const { data } = await api.get(`/bookings/${bookingId}/location`)
  return data
}

// GET /bookings/{booking_id}/location/history?limit= → { booking_id, count, points }
export async function getLocationHistory(bookingId, limit = 100) {
  const { data } = await api.get(`/bookings/${bookingId}/location/history`, {
    params: { limit },
  })
  return data
}

// --- WebSocket URL builders (token via ?token=, per backend contract) ------

// Chat: ws://host/ws/bookings/{id}?token=<JWT>
export function chatSocketUrl(bookingId, token) {
  return `${WS_BASE}/ws/bookings/${bookingId}?token=${encodeURIComponent(token)}`
}

// Location: ws://host/ws/bookings/{id}/location?token=<JWT>
export function locationSocketUrl(bookingId, token) {
  return `${WS_BASE}/ws/bookings/${bookingId}/location?token=${encodeURIComponent(token)}`
}
