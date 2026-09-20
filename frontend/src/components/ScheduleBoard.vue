<template>
  <div class="panel">
    <!-- 场地信息头 -->
    <div class="venue-head">
      <div class="titles">
        <h2>
          {{ venue.name }}
          <span class="badge" :class="STATUS_BADGE[venue.status]">
            {{ VENUE_STATUSES[venue.status] }}
          </span>
        </h2>
        <div class="meta">
          <span>📍 {{ venue.floor?.name }} · 门牌 {{ venue.room_no }}</span>
          <span>👥 可容纳 {{ venue.capacity }} 人</span>
          <span>🏷 {{ VENUE_TYPES[venue.venue_type] }}</span>
          <span v-if="venue.facilities?.length">
            🧰 {{ venue.facilities.map((f) => FACILITIES[f]).join('、') }}
          </span>
        </div>
      </div>
      <div class="spacer" />
      <button class="btn" @click="$emit('edit-venue')">编辑档案</button>
      <button
        class="btn btn-primary"
        :disabled="venue.status !== 'available'"
        :title="venue.status !== 'available' ? '非可订状态不可登记新档期' : '登记一场新档期'"
        @click="openBooking()"
      >
        登记档期
      </button>
    </div>

    <!-- 工具条：日/周切换 + 翻页 -->
    <div class="toolbar">
      <div class="seg">
        <button :class="{ on: view === 'day' }" @click="switchView('day')">日视图</button>
        <button :class="{ on: view === 'week' }" @click="switchView('week')">周视图</button>
      </div>
      <button class="btn btn-small" @click="shift(-1)">
        ‹ 上{{ view === 'day' ? '一天' : '一周' }}
      </button>
      <button class="btn btn-small" @click="goToday">今天</button>
      <button class="btn btn-small" @click="shift(1)">
        下{{ view === 'day' ? '一天' : '一周' }} ›
      </button>
      <div class="date-label">{{ rangeLabel }}</div>
    </div>

    <!-- 错误横幅：跨楼栋、场地不存在等，明确说明，不给空白页 -->
    <div v-if="errorMsg" class="error-banner">
      <span class="code">{{ errorCode }}</span>
      <span>{{ errorMsg }}</span>
      <button @click="errorMsg = ''">×</button>
    </div>

    <div class="schedule-body">
      <div v-if="loading" class="empty-note">档期加载中…</div>

      <template v-else-if="!errorMsg">
        <!-- ============ 日视图（8:00–22:00 时间轴） ============ -->
        <div v-if="view === 'day'" class="day-grid">
          <div class="day-hours" :style="{ height: AXIS_MIN + 'px' }">
            <span
              v-for="h in hourLabels"
              :key="h"
              class="hour-tick"
              :style="{ top: (h - START_HOUR) * 60 + 'px' }"
              >{{ h }}:00</span
            >
          </div>
          <div class="day-track" :style="{ height: AXIS_MIN + 'px' }" @click="onDayClick">
            <div
              v-for="b in dayBars"
              :key="b.id"
              class="booking-bar"
              :style="b.style"
              @click.stop="$emit('booking-click', b.raw)"
            >
              <div class="bt">
                <span v-if="b.continuesFrom" class="cross-tag">◀ 跨天续</span>
                <span v-else-if="b.continuesTo" class="cross-tag">跨天起 ▶</span>
                {{ b.raw.title }}
              </div>
              <div class="bm">
                {{ fmtTime(b.raw.start_at) }} ~ {{ fmtTime(b.raw.end_at) }} ·
                {{ b.raw.organizer }}
              </div>
            </div>
            <div v-if="data?.bookings.length === 0" class="empty-note">
              这一天暂无档期，点击空白时段可直接登记。
            </div>
          </div>
        </div>

        <!-- ============ 周视图（横向甘特：跨天场次一条贯穿多列） ============ -->
        <div v-else>
          <div class="week-grid" :style="{ height: weekGridHeight + 'px' }">
            <div
              v-for="(d, i) in days"
              :key="d.date"
              class="week-cell"
              :class="{ today: d.date === todayStr() }"
              :style="{ height: weekGridHeight + 'px' }"
            >
              <div class="week-head" :class="{ today: d.date === todayStr() }">
                <span>{{ d.label }}</span>
                <span class="wd">{{ d.short }}</span>
              </div>
            </div>
            <div
              v-for="b in weekBars"
              :key="b.id"
              class="week-bar"
              :style="b.style"
              @click="$emit('booking-click', b.raw)"
            >
              <div class="bt">
                <span v-if="b.isCross" class="cross-tag">跨{{ b.spansDays }}天</span>
                {{ b.raw.title }}
              </div>
              <div class="bm">
                {{ fmtTime(b.raw.start_at) }} ~ {{ fmtTime(b.raw.end_at) }} ·
                {{ b.raw.organizer }}
              </div>
            </div>
          </div>
          <div v-if="data?.bookings.length === 0" class="empty-note">本周暂无档期。</div>
          <div class="legend">
            <span><i :style="{ background: 'var(--bar)' }"></i>单天档期</span>
            <span><i :style="{ background: 'var(--bar-2)' }"></i>跨天档期（一条连续贯穿，不切断）</span>
            <span>🕘 每列代表当天 08:00–22:00</span>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { api } from '../api'
import {
  FACILITIES,
  VENUE_STATUSES,
  VENUE_TYPES,
  STATUS_BADGE,
  addDays,
  fmtTime,
  mondayOf,
  todayStr,
  weekdayLabels,
} from '../constants'
import {
  AXIS_MIN,
  END_HOUR,
  HOUR_PX,
  START_HOUR,
  computeDayBars,
  computeWeekBars,
} from '../schedule-geom'

const props = defineProps({
  building: { type: Object, required: true },
  venue: { type: Object, required: true },
})
const emit = defineEmits(['edit-venue', 'booking-click', 'book-slot'])
const hourLabels = Array.from({ length: END_HOUR - START_HOUR + 1 }, (_, i) => START_HOUR + i)

const view = ref('day')
const anchor = ref(todayStr())
const data = ref(null)
const loading = ref(false)
const errorMsg = ref('')
const errorCode = ref('')

const COLORS = ['var(--bar)', 'var(--bar-3)', 'var(--bar-2)']
const CROSS_COLOR = 'var(--bar-2)'

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    data.value = await api.schedule(props.building.id, props.venue.id, view.value, anchor.value)
  } catch (e) {
    errorMsg.value = e.message
    errorCode.value = e.code || `HTTP ${e.status}`
    data.value = null
  } finally {
    loading.value = false
  }
}

function switchView(v) {
  view.value = v
  load()
}
function shift(n) {
  anchor.value = addDays(anchor.value, view.value === 'day' ? n : n * 7)
  load()
}
function goToday() {
  anchor.value = todayStr()
  load()
}
function openBooking() {
  emit('book-slot', null)
}

watch(
  () => props.venue.id,
  () => {
    anchor.value = todayStr()
    view.value = 'day'
    load()
  },
  { immediate: true }
)

// ---------------- 日视图 ----------------
const dayBars = computed(() => {
  if (!data.value) return []
  return computeDayBars(data.value.bookings, data.value.date).map((b, idx) => ({
    ...b,
    style: {
      top: b.top + 'px',
      height: b.heightPx + 'px',
      background:
        b.continuesFrom || b.continuesTo ? CROSS_COLOR : COLORS[idx % COLORS.length],
    },
  }))
})

function onDayClick(ev) {
  if (props.venue.status !== 'available') return
  const rect = ev.currentTarget.getBoundingClientRect()
  const y = ev.clientY - rect.top
  const minutes = Math.round(y / 30) * 30
  const h = START_HOUR + Math.floor(minutes / 60)
  const m = minutes % 60
  if (h >= END_HOUR) return
  const pad = (n) => String(n).padStart(2, '0')
  emit('book-slot', {
    start: `${data.value.date}T${pad(h)}:${pad(m)}`,
    end: `${data.value.date}T${pad(Math.min(h + 1, END_HOUR))}:${pad(m)}`,
  })
}

// ---------------- 周视图（横向甘特） ----------------
const days = computed(() => weekdayLabels(mondayOf(anchor.value)))

const LANE_H = 42
const GRID_HEAD = 34

// 几何在 schedule-geom.js 里用纯函数实现并单测；这里只拼样式
const weekBars = computed(() => {
  if (!data.value) return []
  return computeWeekBars(data.value.bookings, anchor.value).map((it) => ({
    ...it,
    style: {
      left: `calc(${it.leftPct}% + 3px)`,
      width: `calc(${it.widthPct}% - 6px)`,
      top: GRID_HEAD + it.lane * LANE_H + 4 + 'px',
      height: '34px',
      background: it.isCross ? CROSS_COLOR : 'var(--bar)',
      zIndex: it.isCross ? 2 : 1,
    },
  }))
})

const weekGridHeight = computed(() => {
  const lanes = new Set(weekBars.value.map((b) => b.lane)).size
  return GRID_HEAD + Math.max(1, lanes) * LANE_H + 12
})

const rangeLabel = computed(() => {
  if (view.value === 'day') {
    const names = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    return `${anchor.value}（${names[new Date(`${anchor.value}T00:00:00`).getDay()]}）`
  }
  const d = days.value
  return `${d[0].date} ~ ${d[6].date}`
})

defineExpose({ reload: load })
</script>
