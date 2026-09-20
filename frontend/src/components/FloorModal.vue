<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-head">新增楼层 · {{ building.name }}</div>
      <div class="modal-body">
        <div v-if="error" class="form-error">{{ error }}</div>
        <div class="field-row">
          <div class="field">
            <label>楼层数 *</label>
            <input v-model.number="level" type="number" placeholder="如：3（地下填 -1）" />
          </div>
          <div class="field">
            <label>楼层名称 *</label>
            <input v-model="floorName" placeholder="如：3F" />
          </div>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn" @click="$emit('close')">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="submit">保存</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { api } from '../api'

const props = defineProps({ building: { type: Object, required: true } })
const emit = defineEmits(['close', 'saved'])
const level = ref(1)
const floorName = ref('1F')
const error = ref('')
const saving = ref(false)

watch(
  () => level.value,
  (v) => {
    if (Number.isFinite(v)) floorName.value = `${v}F`
  }
)

async function submit() {
  error.value = ''
  if (!Number.isFinite(level.value)) {
    error.value = '楼层数必须是整数。'
    return
  }
  if (!floorName.value.trim()) {
    error.value = '楼层名称必填。'
    return
  }
  saving.value = true
  try {
    await api.createFloor(props.building.id, {
      level: level.value,
      name: floorName.value.trim(),
    })
    emit('saved')
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>
