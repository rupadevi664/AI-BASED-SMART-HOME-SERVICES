import { api } from './api'

// --- Phase 7: AI assistant (Google Gemini, proxied by the backend) ---------
// The GEMINI_API_KEY lives only on the backend; the frontend never sees it.
// We only POST to /llm/chat with the JWT (attached by the api interceptor).

/**
 * Ask the Smart Home AI Assistant.
 * @param {object} args
 * @param {string} args.message        The customer's question (required).
 * @param {Array}  [args.history]      Recent turns, [{ role: 'user'|'assistant', text }]
 *                                     — server caps at GEMINI_MAX_HISTORY_TURNS.
 * @param {string} [args.serviceContext] Optional context, e.g. the page the
 *                                     customer was viewing.
 * @returns {Promise<string>} The assistant's clean reply text.
 */
export async function sendChatMessage({ message, history = [], serviceContext = null }) {
  const payload = { message }
  if (history.length) payload.history = history
  if (serviceContext) payload.service_context = serviceContext
  const { data } = await api.post('/llm/chat', payload)
  return data.response
}
