<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { scheduleApi, buildingsApi } from '../api'
import { useBuildings } from '../buildings-store'
import {
  addDays,
  fmtDateTime,
  mondayOf,
  toISODate,
  WEEKDAY_CN,
} from '../date-utils'

const { state } = useBuildings()
const bid = computed(() => state.buildingId)

const loading = ref(false)
const loadError = ref('')
const data = ref(null)
const floors = ref([])

const view = ref('day') // day | week
const cursor = ref(new Date())
const filterFloor = ref('')
const filterVenue = ref('')

const dayStr = computed(() => toISODate(cursor.value))

const weekDays = computed(() => {
  if (!data.value) return []
  return data.value.days.map((s, i) => {
    const d = new Date(s + 'T00:00:00')
    return {
      date: s,
      label: `${s.slice(5).replace('-', '/')}`,
      weekday: WEEKDAY_CN[(d.getDay() + 6) % 7],
      weekend: i >= 5,
    }
  })
})

const rangeStart = computed(() => data.value && new Date(data.value.range_start))
const rangeEnd = computed(() => data.value && new Date(data.value.range_end))

const WINDOW_MIN = 24 * 60 // 0:00–24:00，跨天凌晨段也能完整画出来

function barGeometry(b) {
  // 以 0~24 点为刻度，把档期映射到视图窗口；跨天档期是一条连续的条，
  // 超出窗口的部分保留真实起止时间并用箭头标出
  const s = new Date(b.start_at)
  const e = new Date(b.end_at)
  const winStart = rangeStart.value
  const winEnd = rangeEnd.value
  const winMin =
    view.value === 'week' ? 7 * WINDOW_MIN : WINDOW_MIN
  const leftMin = Math.max(0, (s - winStart) / 60000)
  const rightMin = Math.min(winMin, (e - winStart) / 60000)
  return {
    left: (leftMin / winMin) * 100,
    width: Math.max(0.8, ((rightMin - leftMin) / winMin) * 100),
    cross: b.starts_before_range || b.ends_after_range || b.touched_dates.length > 1,
  }
}

const venues = computed(() => data.value?.venues ?? [])

function bookingsOf(venueId) {
  return data.value.bookings.filter((b) => b.venue_id === venueId)
}

async function load() {
  if (!bid.value) return
  loading.value = true
  loadError.value = ''
  try {
    const params = { view: view.value, day: dayStr.value }
    if (filterFloor.value) params.floor_id = filterFloor.value
    if (filterVenue.value) params.venue_id = filterVenue.value
    data.value = await scheduleApi.get(bid.value, params)
  } catch (e) {
    // 越楼栋/楼栋失效：挡住并说明原因，绝不展示空白页
    loadError.value = e.message
    data.value = null
  } finally {
    loading.value = false
  }
}

async function loadFloors() {
  if (!bid.value) return
  try {
    floors.value = await buildingsApi.floors(bid.value)
  } catch (e) {
    floors.value = []
  }
}

watch([bid, view], async () => {
  await loadFloors()
  load()
})
watch([dayStr, filterFloor, filterVenue], load)
onMounted(async () => {
  await loadFloors()
  load()
})

function shiftView(delta) {
  cursor.value = addDays(cursor.value, view.value === 'week' ? delta * 7 : delta)
}
function goToday() {
  cursor.value = new Date()
}
function switchView(v) {
  // 切周视图时把光标对齐到周一，避免视觉跳变
  view.value = v
  if (v === 'week') cursor.value = mondayOf(cursor.value)
}

const title = computed(() => {
  if (view.value === 'day') {
    const d = cursor.value
    return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日`
  }
  const mon = mondayOf(cursor.value)
  const sun = addDays(mon, 6)
  return `${mon.getMonth() + 1}/${mon.getDate()} – ${sun.getMonth() + 1}/${sun.getDate()}`
})

// ---------------- 新建档期弹窗 ----------------
const modal = reactive({
  show: false,
  saving: false,
  error: '',
  conflict: null,
  form: { venue_id: null, title: '', booker: '', start_at: '', end_at: '' },
})

function defaultStart() {
  const d = new Date()
  d.setMinutes(d.getMinutes() >= 30 ? 60 : 30, 0, 0)
  return toISODate(d) + 'T' + String(d.getHours()).padStart(2, '0') + ':00'
}

function openCreate(venueId, dateStr) {
  const startDate = dateStr || dayStr.value
  modal.form = {
    venue_id: venueId || filterVenue.value || venues.value[0]?.id || null,
    title: '',
    booker: '',
    start_at: `${startDate}T09:00`,
    end_at: `${startDate}T10:00`,
  }
  modal.error = ''
  modal.conflict = null
  modal.show = true
}

async function submitBooking() {
  modal.saving = true
  modal.error = ''
  modal.conflict = null
  try {
    await scheduleApi.createBooking(bid.value, modal.form.venue_id, {
      title: modal.form.title,
      booker: modal.form.booker,
      start_at: modal.form.start_at,
      end_at: modal.form.end_at,
      remark: '',
    })
    modal.show = false
    await load()
  } catch (e) {
    modal.error = e.message
    modal.conflict = e.details?.occupier ?? null
  } finally {
    modal.saving = false
  }
}

// ---------------- 档期详情/取消 ----------------
const detail = reactive({ show: false, booking: null, busy: false, error: '' })

function openDetail(b) {
  detail.show = true
  detail.booking = b
  detail.error = ''
}

async function cancelBooking() {
  detail.busy = true
  detail.error = ''
  try {
    await scheduleApi.cancel(bid.value, detail.booking.id)
    detail.show = false
    await load()
  } catch (e) {
    detail.error = e.message
  } finally {
    detail.busy = false
  }
}
</script>

<template>
  <section v-if="bid">
    <div class="page-head">
      <div>
        <h2>档期与占用</h2>
        <p class="page-sub">
          {{ state.buildings.find((x) => x.id === bid)?.name }} · 一个时段只属于一个场次
        </p>
      </div>
      <button class="btn primary" :disabled="!venues.length" @click="openCreate()">
        ＋ 登记档期
      </button>
    </div>

    <div class="toolbar panel">
      <div class="seg">
        <button :class="{ on: view === 'day' }" @click="switchView('day')">日视图</button>
        <button :class="{ on: view === 'week' }" @click="switchView('week')">周视图</button>
      </div>
      <div class="pager">
        <button class="btn sm" @click="shiftView(-1)">‹</button>
        <button class="btn sm" @click="goToday">今天</button>
        <button class="btn sm" @click="shiftView(1)">›</button>
        <span class="range-title">{{ title }}</span>
      </div>
      <div class="spacer"></div>
      <select v-model="filterFloor" class="select">
        <option value="">全部楼层</option>
        <option v-for="f in floors" :key="f.id" :value="f.id">{{ f.name }}</option>
      </select>
      <select v-model="filterVenue" class="select">
        <option value="">全部场地</option>
        <option v-for="v in venues" :key="v.id" :value="v.id">{{ v.name }}</option>
      </select>
    </div>

    <div v-if="loadError" class="alert error big">
      <div class="err-title">🚫 无法展示该楼栋的档期</div>
      <div>{{ loadError }}</div>
      <div class="err-hint">请使用顶栏切回您有权查看的楼栋，而不是停留在空白页。</div>
    </div>

    <div v-else-if="data" class="board panel">
      <!-- 表头刻度 -->
      <div class="grid-head">
        <div class="venue-col">场地 \\ 时间</div>
        <div class="track-head" :class="{ week: view === 'week' }">
          <!-- 日视图：小时刻度 -->
          <template v-if="view === 'day'">
            <div
              v-for="h in 24"
              :key="h"
              class="tick"
              :style="{ left: (h / 24) * 100 + '%' }"
            >
              {{ String(h).padStart(2, '0') }}:00
            </div>
          </template>
          <!-- 周视图：7 天 -->
          <template v-else>
            <div
              v-for="(d, i) in weekDays"
              :key="d.date"
              class="day-cell-head"
              :class="{ weekend: d.weekend, today: d.date === toISODate(new Date()) }"
              :style="{ left: (i / 7) * 100 + '%', width: 100 / 7 + '%' }"
            >
              <span class="wk">周{{ d.weekday }}</span>
              <span class="dt">{{ d.label }}</span>
            </div>
          </template>
        </div>
      </div>

      <div v-if="loading" class="board-loading">加载中…</div>
      <div v-else-if="venues.length === 0" class="board-empty">
        当前筛选下没有场地。
      </div>

      <div v-else>
        <div v-for="v in venues" :key="v.id" class="grid-row" :class="{ disabled: v.status !== '可订' }">
          <div class="venue-col venue-cell">
            <div class="vname">{{ v.name }}</div>
            <div class="vsub">
              {{ v.floor_name }} · {{ v.door_plate }} · {{ v.capacity }}人
            </div>
            <div v-if="v.status !== '可订'" class="tag" :class="v.status === '装修中' ? 'warn' : 'off'">
              {{ v.status }}
            </div>
          </div>
          <div class="track" :class="{ week: view === 'week' }" @click="openCreate(v.id, view === 'day' ? dayStr : null)">
            <!-- 网格线 -->
            <template v-if="view === 'day'">
              <div v-for="h in 24" :key="h" class="gridline" :style="{ left: (h / 24) * 100 + '%' }"></div>
            </template>
            <template v-else>
              <div
                v-for="(d, i) in weekDays"
                :key="d.date"
                class="day-gridline"
                :class="{ weekend: d.weekend }"
                :style="{ left: (i / 7) * 100 + '%', width: 100 / 7 + '%' }"
              ></div>
            </template>

            <!-- 档期条：跨天是一条连续的紫边条，不拆段 -->
            <button
              v-for="b in bookingsOf(v.id)"
              :key="b.id"
              class="bar"
              :class="{ cross: barGeometry(b).cross }"
              :style="{ left: barGeometry(b).left + '%', width: barGeometry(b).width + '%' }"
              :title="`${b.title}\n${b.booker}\n${fmtDateTime(b.start_at)} ~ ${fmtDateTime(b.end_at)}`"
              @click.stop="openDetail(b)"
            >
              <span v-if="b.starts_before_range" class="cap">«</span>
              <span class="bar-text">
                <b>{{ b.title }}</b>
                <span class="bar-time">
                  <template v-if="view === 'day'">
                    {{ b.start_at.slice(11, 16) }}–{{ b.end_at.slice(11, 16) }}
                    <em v-if="b.ends_after_range">次日</em>
                  </template>
                  <template v-else>
                    {{ b.start_at.slice(5, 10) }} {{ b.start_at.slice(11, 16) }}
                    → {{ b.end_at.slice(5, 10) }} {{ b.end_at.slice(11, 16) }}
                  </template>
                </span>
              </span>
              <span v-if="b.ends_after_range" class="cap">»</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <p v-if="data" class="legend">
      <span class="dot normal"></span> 普通场次
      <span class="dot cross"></span> 跨天场次（一条连续展示，« / » 表示延伸到视图外）
      <span v-if="data.cached" class="cache-hint">（数据来自缓存）</span>
    </p>

    <!-- 登记档期 -->
    <div v-if="modal.show" class="modal-mask" @click.self="modal.show = false">
      <div class="modal">
        <h3>登记档期</h3>
        <div v-if="modal.error" class="alert error">
          <div>⛔ {{ modal.error }}</div>
          <div v-if="modal.conflict" class="occupy-card">
            <div>当前占用方：</div>
            <div><b>{{ modal.conflict.title }}</b></div>
            <div>预订人：{{ modal.conflict.booker }}</div>
            <div class="mono">
              {{ fmtDateTime(modal.conflict.start_at) }} ~
              {{ fmtDateTime(modal.conflict.end_at) }}
            </div>
            <div class="hint">请避开该时段，或换一间空闲场地后再提交。</div>
          </div>
        </div>
        <div class="form-row">
          <label>场地 *</label>
          <select v-model="modal.form.venue_id" class="select">
            <option v-for="v in venues" :key="v.id" :value="v.id" :disabled="v.status !== '可订'">
              {{ v.floor_name }} · {{ v.name }}{{ v.status !== '可订' ? `（${v.status}）` : '' }}
            </option>
          </select>
        </div>
        <div class="form-row">
          <label>场次名称 *</label>
          <input v-model="modal.form.title" class="input" placeholder="如 产品联合评审" />
        </div>
        <div class="form-row">
          <label>预订人 / 占用方 *</label>
          <input v-model="modal.form.booker" class="input" placeholder="如 王敏" />
        </div>
        <div class="form-grid">
          <div class="form-row">
            <label>开始时间 *</label>
            <input v-model="modal.form.start_at" type="datetime-local" class="input" />
          </div>
          <div class="form-row">
            <label>结束时间 *（可跨天）</label>
            <input v-model="modal.form.end_at" type="datetime-local" class="input" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="modal.show = false">取消</button>
          <button class="btn primary" :disabled="modal.saving" @click="submitBooking">
            {{ modal.saving ? '提交中…' : '提交占用' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 档期详情 -->
    <div v-if="detail.show" class="modal-mask" @click.self="detail.show = false">
      <div class="modal">
        <h3>档期详情</h3>
        <div v-if="detail.error" class="alert error">{{ detail.error }}</div>
        <dl class="detail-list">
          <dt>场次</dt><dd>{{ detail.booking.title }}</dd>
          <dt>预订人</dt><dd>{{ detail.booking.booker }}</dd>
          <dt>场地</dt><dd>{{ detail.booking.venue_name }}</dd>
          <dt>时间</dt>
          <dd class="mono">{{ fmtDateTime(detail.booking.start_at) }} ~ {{ fmtDateTime(detail.booking.end_at) }}</dd>
          <dt>跨天</dt>
          <dd>
            <span v-if="detail.booking.touched_dates.length > 1">
              是，覆盖 {{ detail.booking.touched_dates.join('、') }}
            </span>
            <span v-else>否</span>
          </dd>
        </dl>
        <div class="modal-footer">
          <button class="btn" @click="detail.show = false">关闭</button>
          <button class="btn danger" :disabled="detail.busy" @click="cancelBooking">
            {{ detail.busy ? '处理中…' : '取消该档期' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 16px;
}
.page-head h2 { margin: 0 0 4px; font-size: 20px; }
.page-sub { margin: 0; color: var(--text-3); font-size: 13px; }

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  margin-bottom: 14px;
}
.spacer { flex: 1; }
.seg {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.seg button {
  border: none;
  background: #fff;
  padding: 7px 16px;
  font-size: 13px;
  color: var(--text-2);
}
.seg button.on {
  background: var(--brand);
  color: #fff;
  font-weight: 600;
}
.pager {
  display: flex;
  align-items: center;
  gap: 6px;
}
.range-title {
  margin-left: 8px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.big { font-size: 14px; padding: 18px 20px; }
.err-title { font-size: 15px; font-weight: 700; margin-bottom: 6px; }
.err-hint { margin-top: 8px; opacity: 0.85; }

.board { padding: 0; overflow: auto; }
.grid-head,
.grid-row {
  display: flex;
  align-items: stretch;
}
.grid-head {
  position: sticky;
  top: 0;
  background: #fafbfe;
  z-index: 5;
  border-bottom: 1px solid var(--border);
}
.venue-col {
  width: 210px;
  min-width: 210px;
  padding: 10px 14px;
  border-right: 1px solid var(--border);
}
.track-head {
  position: relative;
  flex: 1;
  height: 38px;
  min-width: 600px;
}
.tick {
  position: absolute;
  top: 12px;
  transform: translateX(-50%);
  font-size: 11px;
  color: var(--text-3);
  font-variant-numeric: tabular-nums;
}
.tick::before {
  content: '';
  display: block;
  width: 1px;
  height: 5px;
  background: var(--border);
  margin: 0 auto -2px;
  transform: translateY(-7px);
}
.day-cell-head {
  position: absolute;
  top: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  border-right: 1px solid var(--border);
}
.day-cell-head .wk { color: var(--text-2); }
.day-cell-head .dt { color: var(--text-3); font-size: 12px; font-variant-numeric: tabular-nums; }
.day-cell-head.weekend { background: #f7f8fc; }
.day-cell-head.today .wk { color: var(--brand); font-weight: 700; }

.grid-row {
  border-bottom: 1px solid var(--border);
  min-height: 58px;
}
.grid-row:last-child { border-bottom: none; }
.grid-row.disabled .track { background: repeating-linear-gradient(
  45deg, #fafbfd, #fafbfd 10px, #f3f5f9 10px, #f3f5f9 20px); }
.venue-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
  justify-content: center;
}
.vname { font-weight: 600; font-size: 13px; }
.vsub { font-size: 11px; color: var(--text-3); }

.track {
  position: relative;
  flex: 1;
  min-width: 600px;
  cursor: cell;
}
.gridline {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: #eef1f6;
}
.day-gridline {
  position: absolute;
  top: 0;
  bottom: 0;
  border-right: 1px solid #eef1f6;
}
.day-gridline.weekend { background: #f9fafd; }

.bar {
  position: absolute;
  top: 7px;
  height: 44px;
  border: none;
  border-radius: 7px;
  background: #e5edff;
  border-left: 3px solid var(--brand);
  color: var(--brand-dark);
  padding: 4px 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  overflow: hidden;
  text-align: left;
  cursor: pointer;
  transition: filter 0.15s;
}
.bar:hover { filter: brightness(0.96); }
.bar.cross {
  background: var(--cross-bg);
  border-left-color: var(--cross);
  color: #5b21b6;
}
.bar-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.bar-text b {
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bar-time {
  font-size: 11px;
  opacity: 0.85;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.bar-time em {
  font-style: normal;
  background: var(--cross);
  color: #fff;
  border-radius: 4px;
  padding: 0 4px;
  margin-left: 4px;
}
.cap { font-weight: 700; font-size: 13px; flex: none; }

.board-loading,
.board-empty {
  padding: 60px;
  text-align: center;
  color: var(--text-3);
}

.legend {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-3);
  font-size: 12px;
  margin: 12px 4px;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  display: inline-block;
  margin: 0 2px 0 10px;
}
.dot.normal { background: #e5edff; border-left: 3px solid var(--brand); }
.dot.cross { background: var(--cross-bg); border-left: 3px solid var(--cross); }
.cache-hint { margin-left: auto; }

.occupy-card {
  margin-top: 8px;
  padding: 10px 12px;
  background: #fff;
  border-radius: 8px;
  line-height: 1.8;
}
.occupy-card .hint { margin-top: 6px; color: var(--danger); }
.mono { font-variant-numeric: tabular-nums; }

.detail-list {
  display: grid;
  grid-template-columns: 70px 1fr;
  gap: 10px 12px;
  margin: 0;
  font-size: 13px;
}
.detail-list dt { color: var(--text-3); }
.detail-list dd { margin: 0; }
</style>
