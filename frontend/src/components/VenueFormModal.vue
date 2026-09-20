<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-head">{{ isEdit ? '编辑场地档案' : '新建场地' }}</div>
      <div class="modal-body">
        <div v-if="error" class="form-error">{{ error }}</div>

        <div class="field-row">
          <div class="field">
            <label>场地名称 *</label>
            <input v-model="form.name" placeholder="如：第一会议室" />
          </div>
          <div class="field">
            <label>门牌号 *</label>
            <input v-model="form.room_no" placeholder="如：A101" />
          </div>
        </div>

        <div class="field-row">
          <div class="field">
            <label>所属楼层 *</label>
            <select v-model="form.floor_id">
              <option v-for="f in building.floors" :key="f.id" :value="f.id">
                {{ f.name }}（{{ f.level }} 层）
              </option>
            </select>
          </div>
          <div class="field">
            <label>容纳人数 *</label>
            <input v-model.number="form.capacity" type="number" min="1" />
          </div>
        </div>

        <div class="field-row">
          <div class="field">
            <label>场地类型 *</label>
            <select v-model="form.venue_type">
              <option v-for="(label, key) in VENUE_TYPES" :key="key" :value="key">
                {{ label }}
              </option>
            </select>
          </div>
          <div class="field">
            <label>状态 *</label>
            <select v-model="form.status">
              <option v-for="(label, key) in VENUE_STATUSES" :key="key" :value="key">
                {{ label }}
              </option>
            </select>
          </div>
        </div>

        <div class="field">
          <label>配套设备</label>
          <div class="check-grid">
            <label v-for="(label, key) in FACILITIES" :key="key">
              <input
                type="checkbox"
                :checked="form.facilities.includes(key)"
                @change="toggleFacility(key)"
              />
              {{ label }}
            </label>
          </div>
        </div>
      </div>
      <div class="modal-foot">
        <button v-if="isEdit" class="btn btn-danger" :disabled="saving" @click="remove">
          删除场地
        </button>
        <div style="flex: 1"></div>
        <button class="btn" @click="$emit('close')">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="submit">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { api } from '../api'
import { FACILITIES, VENUE_STATUSES, VENUE_TYPES } from '../constants'

const props = defineProps({
  building: { type: Object, required: true },
  venue: { type: Object, default: null },
  presetFloorId: { type: Number, default: null },
})
const emit = defineEmits(['close', 'saved', 'deleted'])

const isEdit = !!props.venue
const form = reactive({
  name: props.venue?.name || '',
  room_no: props.venue?.room_no || '',
  floor_id:
    props.venue?.floor_id || props.presetFloorId || props.building.floors[0]?.id,
  capacity: props.venue?.capacity || 10,
  venue_type: props.venue?.venue_type || 'meeting_room',
  facilities: [...(props.venue?.facilities || [])],
  status: props.venue?.status || 'available',
})
const error = ref('')
const saving = ref(false)

function toggleFacility(key) {
  const i = form.facilities.indexOf(key)
  if (i >= 0) form.facilities.splice(i, 1)
  else form.facilities.push(key)
}

async function remove() {
  error.value = ''
  if (!confirm(`确定删除场地「${props.venue.name}」吗？若其名下还有未来档期，系统会拦下。`)) return
  saving.value = true
  try {
    await api.deleteVenue(props.venue.id)
    emit('deleted')
  } catch (e) {
    // 例如 venue_has_future_bookings：后端会说清还有多少场、最早一场是什么
    error.value = e.message
  } finally {
    saving.value = false
  }
}

async function submit() {
  error.value = ''
  if (!form.name.trim()) return (error.value = '请填写场地名称。')
  if (!form.room_no.trim()) return (error.value = '请填写门牌号。')
  if (!form.capacity || form.capacity <= 0) return (error.value = '容纳人数必须大于 0。')
  saving.value = true
  try {
    if (isEdit) {
      await api.updateVenue(props.venue.id, { ...form })
    } else {
      await api.createVenue(props.building.id, {
        building_id: props.building.id,
        ...form,
      })
    }
    emit('saved')
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>
