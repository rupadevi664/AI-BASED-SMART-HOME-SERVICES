import { api } from './api'

// GET /services → [{ id, name, description, base_price, status, created_at }]
export async function listServices() {
  const { data } = await api.get('/services')
  return data
}

// GET /services/{id} → ServiceResponse
export async function getService(id) {
  const { data } = await api.get(`/services/${id}`)
  return data
}

// --- Admin service management (Phase 2) ---------------------------------

// POST /admin/services → ServiceResponse (409 on duplicate name)
export async function createService({ name, description, base_price, status }) {
  const { data } = await api.post('/admin/services', { name, description, base_price, status })
  return data
}

// PUT /admin/services/{id} → ServiceResponse (partial update)
export async function updateService(id, payload) {
  const { data } = await api.put(`/admin/services/${id}`, payload)
  return data
}
