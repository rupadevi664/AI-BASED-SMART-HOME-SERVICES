import { api } from './api'

// GET /bookings/{booking_id}/messages?limit=200 → ASC-ordered chat history.
// Allowed: booking customer + assigned expert (403 for everyone else).
export async function getMessages(bookingId, limit = 200) {
  const { data } = await api.get(`/bookings/${bookingId}/messages`, { params: { limit } })
  return data
}
