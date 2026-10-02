import { useEffect, useState } from 'react'
import { apiError } from '../services/api'
import { createReview, deleteReview, getBookingReview, updateReview } from '../services/reviewService'

const LABELS = { 1: 'Very Poor', 2: 'Poor', 3: 'Good', 4: 'Very Good', 5: 'Excellent' }

export default function ReviewWidget({ bookingId, onDeleted }) {
  const [review, setReview] = useState(null)
  const [loaded, setLoaded] = useState(false)
  const [rating, setRating] = useState(0)
  const [comment, setComment] = useState('')
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    getBookingReview(bookingId)
      .then((r) => {
        if (!alive) return
        setReview(r)
        setRating(r.rating)
        setComment(r.comment || '')
      })
      .catch(() => {}) // 404 = not reviewed yet — the normal case
      .finally(() => alive && setLoaded(true))
    return () => {
      alive = false
    }
  }, [bookingId])

  async function submit() {
    if (!rating) return setError('Pick a star rating first.')
    setBusy(true)
    setError('')
    try {
      if (review) {
        const updated = await updateReview(review.id, { rating, comment })
        setReview(updated)
        setEditing(false)
      } else {
        setReview(await createReview({ booking_id: bookingId, rating, comment }))
        setEditing(false)
      }
    } catch (err) {
      setError(apiError(err))
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!window.confirm('Delete this review?')) return
    setBusy(true)
    try {
      await deleteReview(review.id)
      setReview(null)
      setRating(0)
      setComment('')
      setEditing(false)
      onDeleted?.()
    } catch (err) {
      setError(apiError(err))
    } finally {
      setBusy(false)
    }
  }

  if (!loaded) return null

  // --- Read-only summary (already reviewed, not editing) ---
  if (review && !editing) {
    return (
      <div className="review-widget done">
        <span className="stars" aria-label={`${review.rating} out of 5 stars`}>
          {'★'.repeat(review.rating)}
          <span className="stars-off">{'★'.repeat(5 - review.rating)}</span>
        </span>
        <span className="small muted">{LABELS[review.rating]}</span>
        {review.comment && <p className="small">“{review.comment}”</p>}
        <div className="review-widget-actions">
          <button className="btn btn-outline btn-sm" onClick={() => setEditing(true)}>
            Edit review
          </button>
          <button className="btn btn-outline btn-sm danger" disabled={busy} onClick={remove}>
            Delete
          </button>
        </div>
        {error && <p className="small danger">{error}</p>}
      </div>
    )
  }

  // --- Create / edit form ---
  return (
    <div className="review-widget">
      <p className="small strong">{review ? 'Edit your review' : 'Rate your expert'}</p>
      <div className="stars-input" role="radiogroup" aria-label="Rating">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            className={`star ${n <= rating ? 'on' : ''}`}
            aria-label={`${n} star${n > 1 ? 's' : ''}`}
            onClick={() => setRating(n)}
          >
            ★
          </button>
        ))}
        <span className="small muted">{rating ? LABELS[rating] : 'Pick a rating'}</span>
      </div>
      <textarea
        className="review-comment"
        placeholder="Comment (optional) — e.g. arrived on time, tidy work…"
        maxLength={1000}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
      />
      <div className="review-widget-actions">
        <button className="btn btn-primary btn-sm" disabled={busy} onClick={submit}>
          {review ? 'Save review' : 'Submit review'}
        </button>
        {review && (
          <button className="btn btn-outline btn-sm" disabled={busy} onClick={() => setEditing(false)}>
            Cancel
          </button>
        )}
      </div>
      {error && <p className="small danger">{error}</p>}
    </div>
  )
}
