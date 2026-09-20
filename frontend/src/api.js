// 统一 API 封装：把后端 { error: { code, message } } 信封抛成带中文说明的 Error
async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (res.status === 204) return null
  let body = null
  try {
    body = await res.json()
  } catch {
    /* 非 JSON 响应 */
  }
  if (!res.ok) {
    const message = body?.error?.message || `请求失败（HTTP ${res.status}）`
    const err = new Error(message)
    err.code = body?.error?.code
    err.payload = body?.error
    err.status = res.status
    throw err
  }
  return body
}

export const api = {
  health: () => request('/api/health'),
  listBuildings: () => request('/api/buildings'),
  createBuilding: (data) =>
    request('/api/buildings', { method: 'POST', body: JSON.stringify(data) }),
  createFloor: (buildingId, data) =>
    request(`/api/buildings/${buildingId}/floors`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listVenues: (buildingId) => request(`/api/buildings/${buildingId}/venues`),
  createVenue: (buildingId, data) =>
    request(`/api/buildings/${buildingId}/venues`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateVenue: (venueId, data) =>
    request(`/api/venues/${venueId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteVenue: (venueId) => request(`/api/venues/${venueId}`, { method: 'DELETE' }),

  schedule: (buildingId, venueId, view, date) =>
    request(
      `/api/buildings/${buildingId}/venues/${venueId}/schedule?view=${view}&date=${date}`
    ),
  createBooking: (data) =>
    request('/api/bookings', { method: 'POST', body: JSON.stringify(data) }),
  cancelBooking: (buildingId, bookingId) =>
    request(`/api/buildings/${buildingId}/bookings/${bookingId}/cancel`, {
      method: 'POST',
    }),
}
