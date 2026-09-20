<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-head">登记档期 · {{ venue.name }}</div>
      <div class="modal-body">
        <div v-if="error" class="form-error">
          <div style="font-weight: 600; margin-bottom: 4px">档期没有登记成功</div>
          {{ error }}
          <div v-if="conflict" style="margin-top: 8px; font-size: 12px">
            被占用时段：{{ fmtTime(conflict.conflict_start) }} ~
            {{ fmtTime(conflict.conflict_end) }}
          </div>
        </div>

        <div class="field">
          <label>场次标题 *</label>
          <input v-model="form.title" placeholder="如：季度复盘会" />
        </div>
        <div class="field">
          <label>占用方 / 组织人 *</label>
          <input v-model="form.organizer" placeholder="如：行政部" />
        </div>
        <div class="field-row">
          <div class="field">
            <label>开始时间 *</label>
            <input v-model="form.start" type="datetime-local" />
          </div>
          <div class="field">
            <label>结束时间 *</label>
            <input v-model="form.end" type="datetime-local" />
          </div>
        </div>
        <div style="font-size: 12px; color: var(--ink-faint)">
          支持跨天预订（如今日 14:00 至次日 10:00），日视图与周视图都会完整显示为同一场。
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn" @click="$emit('close')">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="submit">
          {{ saving ? '提交中…' : '提交预订' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { api } from '../api'
import { fmtTime, toLocalInput, todayStr } from '../constants'

const props = defineProps({
  venue: { type: Object, required: true },
  preset: { type: Object, default: null }, // {start: 'YYYY-MM-DDTHH:MM', end}
})
const emit = defineEmits(['close', 'created'])

const defaultStart = props.preset?.start || `${todayStr()}T09:00`
const form = reactive({
  title: '',
  organizer: '',
  start: defaultStart,
  end: props.preset?.end || `${todayStr()}T10:00`,
})
const error = ref('')
const conflict = ref(null)
const saving = ref(false)

async function submit() {
  error.value = ''
  conflict.value = null
  if (!form.title.trim() || !form.organizer.trim()) {
    error.value = '请填写场次标题与占用方。'
    return
  }
  if (!form.start || !form.end || form.end <= form.start) {
    error.value = '结束时间必须晚于开始时间。'
    return
  }
  saving.value = true
  try {
    await api.createBooking({
      venue_id: props.venue.id,
      title: form.title.trim(),
      organizer: form.organizer.trim(),
      // datetime-local 已是本地墙上时间，直接提交 naive 时间，避免 UTC 转换错位
      start_at: form.start.length === 16 ? `${form.start}:00` : form.start,
      end_at: form.end.length === 16 ? `${form.end}:00` : form.end,
    })
    emit('created')
  } catch (e) {
    error.value = e.message
    if (e.code === 'time_conflict') conflict.value = e.payload
  } finally {
    saving.value = false
  }
}
</script>
