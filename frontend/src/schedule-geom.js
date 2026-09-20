// 档期条几何计算（纯函数，便于测试）
// 两种视图都只做「区间与窗口重叠」，跨天场次保持一条记录，不拆行。

import { addDays, isoDate, mondayOf } from './constants'

export const START_HOUR = 8
export const END_HOUR = 22
export const AXIS_MIN = (END_HOUR - START_HOUR) * 60 // 840
export const HOUR_PX = 60

function dayKey(dt) {
  return isoDate(dt)
}

// 时刻在当天 08:00–22:00 窗口内的分钟（夜间夹到端点）
function axisMinutesOf(dt) {
  const m = (dt.getHours() - START_HOUR) * 60 + dt.getMinutes()
  return Math.max(0, Math.min(AXIS_MIN, m))
}

/**
 * 日视图：返回每场在 08:00–22:00 时间轴上的 top/height
 * continuesFrom / continuesTo 标记跨天场次在当日的续/起端
 */
export function computeDayBars(bookings, dateStr) {
  const axisStart = new Date(`${dateStr}T08:00`)
  const axisEnd = new Date(`${dateStr}T22:00`)

  return bookings.map((b, idx) => {
    const s = new Date(b.start_at)
    const e = new Date(b.end_at)
    const continuesFrom = s < axisStart
    const continuesTo = e > axisEnd
    const vs = s < axisStart ? axisStart : s
    const ve = e > axisEnd ? axisEnd : e
    const top = ((vs - axisStart) / 60000) * (HOUR_PX / 60)
    const heightPx = ((ve - vs) / 60000) * (HOUR_PX / 60)
    return { id: b.id, raw: b, continuesFrom, continuesTo, top, heightPx: Math.max(26, heightPx) }
  })
}

/**
 * 周视图：每列代表当天 08:00–22:00，跨天条跨列连续铺设；
 * 夜间(22:00–次日08:00)折叠为列边界，用 2 分钟视觉 ε 让色带跨进相邻列。
 * 返回带泳道（lane）与 left%/width% 的场次条。
 */
export function computeWeekBars(bookings, anchorDateStr) {
  const monday = mondayOf(anchorDateStr)
  const weekStart = new Date(`${monday}T00:00`)
  const viewStart = new Date(`${monday}T08:00`)
  const viewEnd = new Date(`${addDays(monday, 7)}T08:00`)
  const colPct = 100 / 7

  const items = bookings.map((b) => {
    const s0 = new Date(b.start_at)
    const e0 = new Date(b.end_at)
    const vs = s0 < viewStart ? viewStart : s0
    const ve = e0 > viewEnd ? viewEnd : e0
    const startDayIdx = Math.max(0, Math.floor((vs - weekStart) / 86400000))
    const startOffset = axisMinutesOf(vs)

    let axisDur = 0
    let curT = vs.getTime()
    const veT = ve.getTime()
    const s0T = s0.getTime()
    const e0T = e0.getTime()
    for (let guard = 0; guard < 14 && curT < veT; guard++) {
      const dKey = dayKey(new Date(curT))
      const winST = new Date(`${dKey}T08:00`).getTime()
      const winET = new Date(`${dKey}T22:00`).getTime()
      const osT = Math.max(curT, winST)
      const oeT = Math.min(veT, winET)
      if (oeT > osT) {
        axisDur += (oeT - osT) / 60000
        if (osT === winST && s0T < winST) axisDur += 2
        if (oeT === winET && e0T > winET) axisDur += 2
      }
      curT = new Date(`${dKey}T00:00`).getTime() + 86400000
    }

    // 覆盖的自然日数（结束恰好 00:00 不多占一天）
    const sDay = new Date(`${dayKey(s0)}T00:00`).getTime()
    const spansDays = Math.floor((e0.getTime() - 1 - sDay) / 86400000) + 1
    return { id: b.id, raw: b, vs, ve, startDayIdx, startOffset, axisDur, spansDays }
  })

  // 按可视区间重叠关系分泳道
  const sorted = [...items].sort((a, z) => a.vs - z.vs || z.ve - a.ve)
  const laneEnds = []
  return sorted.map((it) => {
    let lane = laneEnds.findIndex((end) => end <= it.vs)
    if (lane === -1) {
      lane = laneEnds.length
      laneEnds.push(it.ve)
    } else {
      laneEnds[lane] = it.ve
    }
    const leftPct = (it.startDayIdx + it.startOffset / AXIS_MIN) * colPct
    const widthPct = (it.axisDur / AXIS_MIN) * colPct
    return {
      ...it,
      lane,
      isCross: it.spansDays > 1,
      leftPct,
      widthPct: Math.max(widthPct, 1.2),
    }
  })
}
