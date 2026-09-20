import { JSDOM } from 'jsdom'
import { readFileSync } from 'node:fs'

const dom = new JSDOM(
  '<!doctype html><html><body><div id="app"></div></body></html>',
  { url: 'http://localhost/', runScripts: 'outside-only' }
)
const { window } = dom

const t = new window.Date()
const p = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate()
  ).padStart(2, '0')}`
const tmw = new window.Date(t)
tmw.setDate(tmw.getDate() + 1)

window.__calls = []
window.fetch = async (url, opts = {}) => {
  const u = String(url)
  window.__calls.push({ method: opts.method || 'GET', url: u, body: opts.body ? JSON.parse(opts.body) : null })
  if (opts.method === 'POST' && u.endsWith('/api/bookings')) {
    const data = JSON.parse(opts.body)
    if (data.title === '必撞的会') {
      return {
        ok: false, status: 409,
        json: async () => ({
          error: {
            code: 'time_conflict',
            message: '时段冲突：已被「研发晨会」（占用方：行政部）占用，请换个时段。',
          },
        }),
      }
    }
    return { ok: true, status: 201, json: async () => ({ id: 99 }) }
  }
  if (opts.method === 'DELETE') {
    return {
      ok: false, status: 409,
      json: async () => ({
        error: {
          code: 'venue_has_future_bookings',
          message: '场地「第一会议室」名下还有 2 场未结束的档期，请先取消这些档期后再删除场地。',
          future_count: 2,
        },
      }),
    }
  }
  if (u.includes('/schedule')) {
    return {
      ok: true, status: 200,
      json: async () => ({
        view: u.includes('week') ? 'week' : 'day', date: p(t),
        range_start: `${p(t)}T00:00:00`, range_end: `${p(tmw)}T00:00:00`,
        venue: {
          id: 101, name: '第一会议室', room_no: 'A101', capacity: 12,
          venue_type: 'meeting_room', facilities: ['projector', 'whiteboard'],
          status: 'available', building_id: 1, floor_id: 12,
          floor: { id: 12, level: 2, name: '2F' },
        },
        bookings: [
          { id: 1, venue_id: 101, title: '研发晨会', organizer: '行政部', status: 'confirmed',
            start_at: `${p(t)}T09:00:00`, end_at: `${p(t)}T10:30:00` },
          { id: 2, venue_id: 101, title: '产品封闭评审（跨天）', organizer: '产品组',
            status: 'confirmed', start_at: `${p(t)}T14:00:00`, end_at: `${p(tmw)}T10:00:00` },
        ],
        cached: false,
      }),
    }
  }
  return { ok: true, status: 200, json: async () => ({}) }
}
window.confirm = () => true

const code = readFileSync('/tmp/huitang-test-build/suite.js', 'utf8')
window.eval(code)
const ok = await window.__suite
process.exit(ok ? 0 : 1)
