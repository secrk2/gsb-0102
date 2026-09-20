export const VENUE_TYPES = {
  meeting_room: '会议室',
  roadshow_hall: '路演厅',
  training_room: '培训室',
  event_space: '活动场地',
}

export const VENUE_STATUSES = {
  available: '可订',
  renovating: '装修中',
  disabled: '停用',
}

export const STATUS_BADGE = {
  available: 'badge-green',
  renovating: 'badge-amber',
  disabled: 'badge-gray',
}

export const FACILITIES = {
  projector: '投影',
  video_conf: '视频会议',
  whiteboard: '白板',
}

export function pad(n) {
  return String(n).padStart(2, '0')
}

// 本地日期 YYYY-MM-DD
export function isoDate(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function todayStr() {
  return isoDate(new Date())
}

export function addDays(dateStr, n) {
  const d = new Date(`${dateStr}T00:00:00`)
  d.setDate(d.getDate() + n)
  return isoDate(d)
}

// 该日所在周的周一
export function mondayOf(dateStr) {
  const d = new Date(`${dateStr}T00:00:00`)
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7))
  return isoDate(d)
}

export function weekdayLabels(startDateStr) {
  const names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  return names.map((n, i) => {
    const ds = addDays(startDateStr, i)
    return { date: ds, label: n, short: ds.slice(5) }
  })
}

// 'YYYY-MM-DDTHH:MM' -> datetime-local 输入框值
export function toLocalInput(iso) {
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours()
  )}:${pad(d.getMinutes())}`
}

export function fmtTime(iso) {
  const d = new Date(iso)
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(
    d.getMinutes()
  )}`
}

export function fmtHM(iso) {
  const d = new Date(iso)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}
