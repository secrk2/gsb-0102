// 后端接口统一封装；业务错误抛出带 code/message/details 的对象，页面直接展示
const BASE = '/api'

export class ApiException extends Error {
  constructor(status, payload) {
    super(payload?.error?.message || `请求失败（HTTP ${status}）`)
    this.status = status
    this.code = payload?.error?.code || 'unknown'
    this.details = payload?.error?.details || null
  }
}

async function request(method, path, body) {
  const res = await fetch(BASE + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new ApiException(res.status, data)
  return data
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b) => request('POST', p, b),
  put: (p, b) => request('PUT', p, b),
  del: (p) => request('DELETE', p),
}

export const buildingsApi = {
  list: () => api.get('/buildings'),
  floors: (bid) => api.get(`/buildings/${bid}/floors`),
}

export const venuesApi = {
  list: (bid, params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null),
    ).toString()
    return api.get(`/buildings/${bid}/venues${qs ? `?${qs}` : ''}`)
  },
  meta: (bid) => api.get(`/buildings/${bid}/venues/meta`),
  create: (bid, body) => api.post(`/buildings/${bid}/venues`, body),
  update: (bid, id, body) => api.put(`/buildings/${bid}/venues/${id}`, body),
  remove: (bid, id) => api.del(`/buildings/${bid}/venues/${id}`),
}

export const scheduleApi = {
  get: (bid, params) => {
    const qs = new URLSearchParams(params).toString()
    return api.get(`/buildings/${bid}/schedule?${qs}`)
  },
  createBooking: (bid, venueId, body) =>
    api.post(`/buildings/${bid}/venues/${venueId}/bookings`, body),
  cancel: (bid, bookingId) =>
    api.post(`/buildings/${bid}/bookings/${bookingId}/cancel`),
}
