<template>
  <div>
    <header class="app-header">
      <span class="logo">汇堂</span>
      <span class="sub">园区场地档期平台</span>
      <div style="flex: 1"></div>
      <span class="sub" :title="`API: ${health.redis ? 'MySQL + Redis 正常' : 'Redis 连接异常'}`">
        ● {{ health.loading ? '检测中' : health.ok && health.redis ? '运行正常' : '依赖异常' }}
      </span>
    </header>

    <div class="layout">
      <BuildingTree
        :buildings="buildings"
        :venues-by-building="venuesByBuilding"
        :current-building-id="selectedBuildingId"
        :current-venue-id="selectedVenueId"
        @select-building="onSelectBuilding"
        @select-venue="onSelectVenue"
        @add-building="openBuildingModal"
        @add-floor="openFloorModal"
        @add-venue="openVenueCreate"
      />

      <main class="main">
        <!-- 全局提示（加载楼栋失败等） -->
        <div v-if="fatalError" class="error-banner" style="margin: 0">
          <span class="code">ERROR</span>
          <span>{{ fatalError }}</span>
        </div>

        <!-- 还没选具体场地：展示楼栋概况 -->
        <div v-if="!selectedVenue && selectedBuildingId" class="panel welcome">
          <div class="big">已选择「{{ currentBuilding?.name }}」</div>
          <div>从左侧选择一间场地查看档期，或为该楼栋添加楼层、新建场地。</div>
          <div style="margin-top: 14px; display: flex; gap: 10px; justify-content: center">
            <button class="btn" @click="openFloorModal(currentBuilding)">＋ 新增楼层</button>
            <button
              class="btn btn-primary"
              :disabled="!currentBuilding?.floors?.length"
              @click="openVenueCreate({ building: currentBuilding, floor: currentBuilding.floors[0] })"
            >
              ＋ 新建场地
            </button>
          </div>
        </div>

        <ScheduleBoard
          v-if="selectedVenue && selectedBuilding"
          ref="boardRef"
          :key="selectedVenue.id"
          :building="selectedBuilding"
          :venue="selectedVenue"
          @edit-venue="openVenueEdit"
          @book-slot="openBookingCreate"
          @booking-click="openBookingDetail"
        />
      </main>
    </div>

    <!-- 新楼栋 -->
    <BuildingModal v-if="buildingModal.show" @close="buildingModal.show = false" @saved="onBuildingsChanged" />

    <!-- 新楼层 -->
    <FloorModal
      v-if="floorModal.show"
      :building="floorModal.building"
      @close="floorModal.show = false"
      @saved="onBuildingsChanged"
    />

    <!-- 场地增改删 -->
    <VenueFormModal
      v-if="venueModal.show"
      :building="venueModal.building"
      :venue="venueModal.venue"
      :preset-floor-id="venueModal.presetFloorId"
      @close="venueModal.show = false"
      @saved="onVenueSaved"
      @deleted="onVenueDeleted"
    />

    <!-- 预订弹窗 -->
    <BookingModal
      v-if="bookingModal.show"
      :venue="bookingModal.venue"
      :preset="bookingModal.preset"
      @close="bookingModal.show = false"
      @created="onBookingCreated"
    />

    <!-- 档期详情 -->
    <BookingDetailModal
      v-if="detailModal.show"
      :building="selectedBuilding"
      :booking="detailModal.booking"
      :venue-name="selectedVenue?.name"
      @close="detailModal.show = false"
      @changed="onBookingChanged"
    />

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from './api'
import BuildingTree from './components/BuildingTree.vue'
import ScheduleBoard from './components/ScheduleBoard.vue'
import VenueFormModal from './components/VenueFormModal.vue'
import BookingModal from './components/BookingModal.vue'
import BookingDetailModal from './components/BookingDetailModal.vue'
import BuildingModal from './components/BuildingModal.vue'
import FloorModal from './components/FloorModal.vue'

const buildings = ref([])
const venuesByBuilding = reactive({})
const selectedBuildingId = ref(null)
const selectedVenueId = ref(null)
const fatalError = ref('')
const toast = ref('')
const boardRef = ref(null)

const selectedBuilding = computed(
  () => buildings.value.find((b) => b.id === selectedBuildingId.value) || null
)
// 树是按 buildingId 拉的场地列表；当前场地从其中找，保证拿到最新 floor 信息
const selectedVenue = computed(() => {
  const list = venuesByBuilding[selectedBuildingId.value] || []
  return list.find((v) => v.id === selectedVenueId.value) || null
})
const currentBuilding = selectedBuilding

const buildingModal = reactive({ show: false })
const floorModal = reactive({ show: false, building: null })
const venueModal = reactive({ show: false, building: null, venue: null })
const bookingModal = reactive({ show: false, venue: null, preset: null })
const detailModal = reactive({ show: false, booking: null })

const health = reactive({ loading: true, ok: false, redis: false })

function showToast(msg) {
  toast.value = msg
  setTimeout(() => (toast.value = ''), 2200)
}

async function checkHealth() {
  try {
    const h = await api.health()
    health.ok = h.api === 'ok'
    health.redis = !!h.redis
  } catch {
    health.ok = false
    health.redis = false
  } finally {
    health.loading = false
  }
}

async function loadBuildings() {
  fatalError.value = ''
  try {
    buildings.value = await api.listBuildings()
    if (!selectedBuildingId.value && buildings.value.length) {
      // 默认进入第一栋楼，但不预选具体场地
      selectedBuildingId.value = buildings.value[0].id
      await loadVenues(selectedBuildingId.value)
    }
  } catch (e) {
    fatalError.value = `楼栋数据加载失败：${e.message}`
  }
}

async function loadVenues(buildingId) {
  try {
    venuesByBuilding[buildingId] = await api.listVenues(buildingId)
  } catch (e) {
    // 404 楼栋不存在等：说清原因，而不是渲染空白
    fatalError.value = e.message
    venuesByBuilding[buildingId] = []
  }
}

async function onSelectBuilding(id) {
  selectedBuildingId.value = id
  selectedVenueId.value = null
  fatalError.value = ''
  if (!venuesByBuilding[id]) await loadVenues(id)
}

async function onSelectVenue({ venue }) {
  selectedVenueId.value = venue.id
}

// ---------- 弹窗 ----------
function openBuildingModal() {
  buildingModal.show = true
}
function openFloorModal(b) {
  if (!b) return
  floorModal.building = b
  floorModal.show = true
}
function openVenueCreate({ building, floor }) {
  venueModal.building = building
  venueModal.venue = null
  // 让弹窗默认选中触发的楼层：通过临时对象传 floor id
  venueModal.presetFloorId = floor?.id
  venueModal.show = true
}
function openVenueEdit() {
  venueModal.building = selectedBuilding.value
  venueModal.venue = selectedVenue.value
  venueModal.show = true
}
function openBookingCreate(preset) {
  bookingModal.venue = selectedVenue.value
  bookingModal.preset = preset
  bookingModal.show = true
}
function openBookingDetail(booking) {
  detailModal.booking = booking
  detailModal.show = true
}

// ---------- 变更回调 ----------
async function onBuildingsChanged() {
  buildingModal.show = false
  floorModal.show = false
  await loadBuildings()
  // list_buildings 已 selectinload floors，直接全量刷新即可
  buildings.value.forEach(async (b) => {
    if (venuesByBuilding[b.id]) await loadVenues(b.id)
  })
}

async function onVenueSaved() {
  venueModal.show = false
  showToast('场地档案已保存')
  await loadVenues(selectedBuildingId.value)
  boardRef.value?.reload()
}

async function onVenueDeleted() {
  venueModal.show = false
  selectedVenueId.value = null
  showToast('场地已删除')
  await loadVenues(selectedBuildingId.value)
}

async function onBookingCreated() {
  bookingModal.show = false
  showToast('档期登记成功')
  boardRef.value?.reload()
}

async function onBookingChanged() {
  detailModal.show = false
  showToast('档期已取消')
  boardRef.value?.reload()
}

onMounted(async () => {
  await checkHealth()
  await loadBuildings()
})
</script>
