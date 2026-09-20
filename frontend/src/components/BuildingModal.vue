<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-head">新增楼栋</div>
      <div class="modal-body">
        <div v-if="error" class="form-error">{{ error }}</div>
        <div class="field">
          <label>楼栋名称 *</label>
          <input v-model="name" placeholder="如：汇智楼" />
        </div>
        <div class="field">
          <label>楼栋编号 *</label>
          <input v-model="code" placeholder="如：HZ_A（唯一）" />
        </div>
        <div style="font-size: 12px; color: var(--ink-faint)">
          新建楼栋后请继续为它添加楼层，场地必须挂在具体楼层下。
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
import { ref } from 'vue'
import { api } from '../api'

const emit = defineEmits(['close', 'saved'])
const name = ref('')
const code = ref('')
const error = ref('')
const saving = ref(false)

async function submit() {
  error.value = ''
  if (!name.value.trim() || !code.value.trim()) {
    error.value = '楼栋名称和编号都必填。'
    return
  }
  saving.value = true
  try {
    await api.createBuilding({ name: name.value.trim(), code: code.value.trim() })
    emit('saved')
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>
