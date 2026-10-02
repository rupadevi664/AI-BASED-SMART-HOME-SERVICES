import { api } from './api'

// --- Phase 6: reviews & ratings --------------------------------------------

// POST /reviews { booking_id, rating, comment } (CUSTOMER who owns the booking)
export async function createReview({ booking_id, rating, comment }) {
  const { data } = await api.post('/reviews', { booking_id, rating, comment })
  return data
}

// GET /reviews/expert/{expert_id} — public: reviews + average + count
export async function getExpertReviews(expertId) {
  const { data } = await api.get(`/reviews/expert/${expertId}`)
  return data
}

// GET /reviews/booking/{booking_id} — the review for one booking (participants)
export async function getBookingReview(bookingId) {
  const { data } = await api.get(`/reviews/booking/${bookingId}`)
  return data
}

// PUT /reviews/{id} { rating?, comment? } (author only)
export async function updateReview(reviewId, { rating, comment }) {
  const { data } = await api.put(`/reviews/${reviewId}`, { rating, comment })
  return data
}

// DELETE /reviews/{id} (author or ADMIN)
export async function deleteReview(reviewId) {
  await api.delete(`/reviews/${reviewId}`)
  return true
}
