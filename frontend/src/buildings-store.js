import { reactive, readonly } from 'vue'
import { buildingsApi } from './api'

// 全局：楼栋列表 + 当前选中楼栋（写入 localStorage，跨页保留）
const state = reactive({
  ready: false,
  loadError: '',
  buildings: [],
  buildingId: Number(localStorage.getItem('huitang:buildingId')) || null,
})

async function loadBuildings() {
  state.ready = false
  state.loadError = ''
  try {
    state.buildings = await buildingsApi.list()
    if (!state.buildings.some((b) => b.id === state.buildingId)) {
      state.buildingId = state.buildings[0]?.id ?? null
      persist()
    }
  } catch (e) {
    state.loadError = e.message
  } finally {
    state.ready = true
  }
}

function setBuilding(id) {
  state.buildingId = id
  persist()
}

function persist() {
  if (state.buildingId)
    localStorage.setItem('huitang:buildingId', String(state.buildingId))
}

export function useBuildings() {
  return { state: readonly(state), loadBuildings, setBuilding }
}
