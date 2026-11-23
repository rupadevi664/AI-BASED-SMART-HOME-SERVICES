import { api } from './api'

export async function getNotifications(unreadOnly = false, limit = 50) {
  const { data } = await api.get('/notifications', {
    params: { unread_only: unreadOnly, limit },
  })
  return data
}

export async function getUnreadCount() {
  const { data } = await api.get('/notifications/unread-count')
  return data.count
}

export async function markAsRead(notificationId) {
  const { data } = await api.patch(`/notifications/${notificationId}/read`)
  return data
}

export async function markAllAsRead() {
  const { data } = await api.post('/notifications/read-all')
  return data
}

export async function deleteNotification(notificationId) {
  const { data } = await api.delete(`/notifications/${notificationId}`)
  return data
}
