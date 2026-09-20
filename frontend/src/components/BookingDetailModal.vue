<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-head">档期详情</div>
      <div class="modal-body">
        <div v-if="error" class="form-error">{{ error }}</div>
        <h3 style="margin: 0">{{ booking.title }}</h3>
        <div class="kv"><span>占用方</span><b>{{ booking.organizer }}</b></div>
        <div class="kv"><span>场地</span><b>{{ booking.venue_name || venueName }}</b></div>
        <div class="kv">
          <span>开始</span><b>{{ fmtFull(booking.start_at) }}</b>
        </div>
        <div class="kv">
          <span>结束</span><b>{{ fmtFull(booking.end_at) }}</b>
        </div>
        <div class="kv">
          <span>时长</span><b>{{ durationText }}</b>
        </div>
        <div v-if="isCross" style="font-size: 12px; color: var(--warn)">
          ⚠ 这是一场跨天档期，在日视图的每一天、周视图中均为同一条完整记录。
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn" @click="$emit('close')">关闭</button>
        <button class="btn btn-danger" :disabled="canceling" @click="cancel">
          {{ canceling ? '取消中…' : '取消该档期' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { api } from '../api'

const props = defineProps({
  building: { type: Object, required: true },
  booking: { type: Object, required: true },
  venueName: { type: String, default: '' },
})
const emit = defineEmits(['close', 'changed'])

const error = ref('')
const canceling = ref(false)

const isCross = computed(() => {
  const s = new Date(props.booking.start_at)
  const e = new Date(props.booking.end_at)
  const p = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
      d.getDate()
    ).padStart(2, '0')}`
  return p(s) !== p(e)
})

const durationText = computed(() => {
  const ms = new Date(props.booking.end_at) - new Date(props.booking.start_at)
  const mins = Math.round(ms / 60000)
  const d = Math.floor(mins / 1440)
  const h = Math.floor((mins % 1440) / 60)
  const m = mins % 60
  return [d && `${d}天`, h && `${h}小时`, m && `${m}分钟`].filter(Boolean).join(' ')
})

function fmtFull(iso) {
  const d = new Date(iso)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(
    d.getMinutes()
  )}`
}

async function cancel() {
  error.value = ''
  if (!confirm(`确定取消档期「${props.booking.title}」吗？`)) return
  canceling.value = true
  try {
    await api.cancelBooking(props.building.id, props.booking.id)
    emit('changed')
  } catch (e) {
    error.value = e.message
  } finally {
    canceling.value = false
  }
}
</script>

<style scoped>
.kv {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px dashed var(--line);
  padding: 7px 2px;
  font-size: 13px;
}
.kv span {
  color: var(--ink-faint);
}
</style>
