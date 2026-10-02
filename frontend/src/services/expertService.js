import { api } from './api'

// GET /experts/nearby?latitude&longitude&radius_km&service_id&availability
// → [{ expert_id, user_id, name, skills, experience_years, location,
//      latitude, longitude, availability, verification_status,
//      distance_km, services: [{id, name}] }]
export async function getNearbyExperts({ latitude, longitude, radiusKm, serviceId, availability }) {
  const params = { latitude, longitude, radius_km: radiusKm }
  if (serviceId) params.service_id = serviceId
  if (availability) params.availability = availability
  const { data } = await api.get('/experts/nearby', { params })
  return data
}

// GET /experts/profile → expert's own full profile (EXPERT only)
export async function getMyProfile() {
  const { data } = await api.get('/experts/profile')
  return data
}

// PUT /experts/profile (partial; service_ids replaces the offered services)
export async function updateMyProfile(payload) {
  const { data } = await api.put('/experts/profile', payload)
  return data
}

// GET /admin/experts → [ExpertProfileResponse] (ADMIN only)
export async function adminListExperts() {
  const { data } = await api.get('/admin/experts')
  return data
}

// PUT /admin/experts/{id}/verification?verification_status=VERIFIED|REJECTED|PENDING
export async function adminSetVerification(expertProfileId, status) {
  const { data } = await api.put(
    `/admin/experts/${expertProfileId}/verification`,
    null,
    { params: { verification_status: status } },
  )
  return data
}
