// 日期小工具：周视图按周一~周日
export function toISODate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function parseISODate(s) {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function addDays(d, n) {
  const x = new Date(d)
  x.setDate(x.getDate() + n)
  return x
}

export function mondayOf(d) {
  const x = new Date(d)
  const delta = (x.getDay() + 6) % 7 // 周一=0 … 周日=6
  x.setDate(x.getDate() - delta)
  return x
}

export const WEEKDAY_CN = ['一', '二', '三', '四', '五', '六', '日']

export function fmtTime(iso) {
  // iso: 2026-09-20T14:00
  return iso.slice(11, 16)
}

export function fmtDateTime(iso) {
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)}`
}

// 把 yyyy-mm-dd + HH:MM 拼成后端要的 datetime-local 值/ISO
export function toInputDT(dateStr, hm) {
  return `${dateStr}T${hm}`
}
