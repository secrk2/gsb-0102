<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { venuesApi, buildingsApi } from '../api'
import { useBuildings } from '../buildings-store'

const { state } = useBuildings()
const bid = computed(() => state.buildingId)

const loading = ref(false)
const loadError = ref('')
const venues = ref([])
const floors = ref([])
const meta = ref({ venue_types: [], venue_status: [], equipment_items: [] })

const filters = reactive({ floor_id: '', status: '', q: '' })

const STATUS_CLASS = { 可订: 'ok', 装修中: 'warn', 停用: 'off' }

async function loadAll() {
  if (!bid.value) return
  loading.value = true
  loadError.value = ''
  try {
    const [vs, fs, m] = await Promise.all([
      venuesApi.list(bid.value, filters),
      buildingsApi.floors(bid.value),
      venuesApi.meta(bid.value),
    ])
    venues.value = vs
    floors.value = fs
    meta.value = m
  } catch (e) {
    // 跨楼栋/楼栋失效等：明确提示，不给空白表格
    loadError.value = e.message
  } finally {
    loading.value = false
  }
}

watch(bid, loadAll)
onMounted(loadAll)

// ---------------- 新建/编辑弹窗 ----------------
const modal = reactive({
  show: false,
  mode: 'create',
  saving: false,
  error: '',
  form: emptyForm(),
})

function emptyForm() {
  return {
    id: null,
    floor_id: null,
    name: '',
    door_plate: '',
    capacity: 10,
    venue_type: '会议室',
    equipment: [],
    status: '可订',
  }
}

function openCreate() {
  Object.assign(modal.form, emptyForm(), {
    floor_id: floors.value[0]?.id ?? null,
  })
  modal.mode = 'create'
  modal.error = ''
  modal.show = true
}

function openEdit(v) {
  Object.assign(modal.form, { ...v, equipment: [...v.equipment] })
  modal.mode = 'edit'
  modal.error = ''
  modal.show = true
}

function toggleEquip(item) {
  const f = modal.form
  const i = f.equipment.indexOf(item)
  if (i >= 0) f.equipment.splice(i, 1)
  else f.equipment.push(item)
}

async function submit() {
  modal.saving = true
  modal.error = ''
  const body = { ...modal.form }
  delete body.id
  try {
    if (modal.mode === 'create') await venuesApi.create(bid.value, body)
    else await venuesApi.update(bid.value, modal.form.id, body)
    modal.show = false
    await loadAll()
  } catch (e) {
    modal.error = friendly(e)
  } finally {
    modal.saving = false
  }
}

// ---------------- 删除（带未来档期保护） ----------------
const delDialog = reactive({ show: false, venue: null, error: '', detail: null })

function askDelete(v) {
  delDialog.show = true
  delDialog.venue = v
  delDialog.error = ''
  delDialog.detail = null
}

async function confirmDelete() {
  delDialog.error = ''
  try {
    await venuesApi.remove(bid.value, delDialog.venue.id)
    delDialog.show = false
    await loadAll()
  } catch (e) {
    // 409 venue_has_future_bookings：展示后端给出的占用详情
    delDialog.error = e.message
    delDialog.detail = e.details?.earliest ?? null
  }
}

function friendly(e) {
  if (e.status === 422) {
    return '提交内容有误：' + (e.message || '请检查表单字段')
  }
  return e.message
}
</script>

<template>
  <section v-if="bid">
    <div class="page-head">
      <div>
        <h2>场地档案</h2>
        <p class="page-sub">
          当前楼栋：<b>{{ state.buildings.find((x) => x.id === bid)?.name }}</b>
        </p>
      </div>
      <button class="btn primary" @click="openCreate">＋ 新建场地</button>
    </div>

    <div class="filters panel">
      <select v-model="filters.floor_id" class="select" @change="loadAll">
        <option value="">全部楼层</option>
        <option v-for="f in floors" :key="f.id" :value="f.id">
          {{ f.name }}
        </option>
      </select>
      <select v-model="filters.status" class="select" @change="loadAll">
        <option value="">全部状态</option>
        <option v-for="s in meta.venue_status" :key="s" :value="s">{{ s }}</option>
      </select>
      <input
        v-model="filters.q"
        class="input"
        placeholder="搜场地名 / 门牌号"
        @keyup.enter="loadAll"
      />
      <button class="btn" @click="loadAll">查询</button>
    </div>

    <div v-if="loadError" class="alert error">
      场地列表加载失败：{{ loadError }}
    </div>

    <div v-else class="panel table-wrap">
      <table class="venue-table">
        <thead>
          <tr>
            <th>楼层</th>
            <th>门牌号</th>
            <th>场地名称</th>
            <th>类型</th>
            <th>容纳人数</th>
            <th>配套设备</th>
            <th>状态</th>
            <th class="col-ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="8" class="muted center">加载中…</td>
          </tr>
          <tr v-else-if="venues.length === 0">
            <td colspan="8" class="muted center">该楼栋下暂无场地，点右上角新建。</td>
          </tr>
          <tr v-for="v in venues" :key="v.id">
            <td>{{ v.floor_name }}</td>
            <td class="mono">{{ v.door_plate }}</td>
            <td class="venue-name">{{ v.name }}</td>
            <td><span class="tag type">{{ v.venue_type }}</span></td>
            <td>{{ v.capacity }} 人</td>
            <td>
              <template v-if="v.equipment.length">
                <span v-for="e in v.equipment" :key="e" class="tag equip">{{ e }}</span>
              </template>
              <span v-else class="muted">—</span>
            </td>
            <td>
              <span class="tag" :class="STATUS_CLASS[v.status]">{{ v.status }}</span>
            </td>
            <td class="col-ops">
              <button class="btn sm" @click="openEdit(v)">编辑</button>
              <button class="btn sm danger" @click="askDelete(v)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新建/编辑 -->
    <div v-if="modal.show" class="modal-mask" @click.self="modal.show = false">
      <div class="modal">
        <h3>{{ modal.mode === 'create' ? '新建场地' : '编辑场地' }}</h3>
        <div v-if="modal.error" class="alert error">{{ modal.error }}</div>
        <div class="form-grid">
          <div class="form-row">
            <label>所在楼层 *</label>
            <select v-model="modal.form.floor_id" class="select">
              <option v-for="f in floors" :key="f.id" :value="f.id">
                {{ f.name }}
              </option>
            </select>
          </div>
          <div class="form-row">
            <label>门牌号 *</label>
            <input v-model="modal.form.door_plate" class="input" placeholder="如 301" />
          </div>
          <div class="form-row">
            <label>场地名称 *</label>
            <input v-model="modal.form.name" class="input" placeholder="如 第一会议室" />
          </div>
          <div class="form-row">
            <label>容纳人数</label>
            <input
              v-model.number="modal.form.capacity"
              type="number"
              min="0"
              class="input"
            />
          </div>
          <div class="form-row">
            <label>场地类型 *</label>
            <select v-model="modal.form.venue_type" class="select">
              <option v-for="t in meta.venue_types" :key="t" :value="t">
                {{ t }}
              </option>
            </select>
          </div>
          <div class="form-row">
            <label>状态</label>
            <select v-model="modal.form.status" class="select">
              <option v-for="s in meta.venue_status" :key="s" :value="s">
                {{ s }}
              </option>
            </select>
          </div>
        </div>
        <div class="form-row">
          <label>配套设备</label>
          <div class="checkbox-group">
            <label v-for="e in meta.equipment_items" :key="e">
              <input
                type="checkbox"
                :checked="modal.form.equipment.includes(e)"
                @change="toggleEquip(e)"
              />
              {{ e }}
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="modal.show = false">取消</button>
          <button class="btn primary" :disabled="modal.saving" @click="submit">
            {{ modal.saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 删除确认 -->
    <div v-if="delDialog.show" class="modal-mask" @click.self="delDialog.show = false">
      <div class="modal">
        <h3>删除场地</h3>
        <template v-if="!delDialog.error">
          <p>
            确定删除场地「<b>{{ delDialog.venue?.name }}</b
            >」（{{ delDialog.venue?.floor_name }} · {{ delDialog.venue?.door_plate }}）吗？
          </p>
          <p class="muted">
            若该场地名下还有未结束的档期，系统会拦下本次删除。
          </p>
        </template>
        <div v-else class="alert error">
          <div>⚠ {{ delDialog.error }}</div>
          <div v-if="delDialog.detail" class="occupy-card">
            <div>被占用的最早档期：</div>
            <div><b>{{ delDialog.detail.title }}</b></div>
            <div>预订人：{{ delDialog.detail.booker }}</div>
            <div class="mono">
              {{ delDialog.detail.start_at }} ~ {{ delDialog.detail.end_at }}
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="delDialog.show = false">
            {{ delDialog.error ? '知道了' : '取消' }}
          </button>
          <button
            v-if="!delDialog.error"
            class="btn danger"
            @click="confirmDelete"
          >
            确认删除
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
.page-head h2 {
  margin: 0 0 4px;
  font-size: 20px;
}
.page-sub {
  margin: 0;
  color: var(--text-3);
  font-size: 13px;
}
.filters {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  margin-bottom: 16px;
}
.filters .input {
  min-width: 200px;
}
.table-wrap {
  overflow: auto;
}
.venue-table {
  width: 100%;
  border-collapse: collapse;
}
.venue-table th,
.venue-table td {
  text-align: left;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  white-space: nowrap;
}
.venue-table th {
  color: var(--text-3);
  font-weight: 500;
  background: #fafbfe;
}
.venue-table tbody tr:last-child td {
  border-bottom: none;
}
.venue-table tbody tr:hover {
  background: #f8faff;
}
.venue-name {
  font-weight: 600;
}
.col-ops {
  display: flex;
  gap: 8px;
}
.col-ops .btn {
  margin-right: 8px;
}
.muted {
  color: var(--text-3);
}
.center {
  text-align: center;
  padding: 32px !important;
}
.mono {
  font-variant-numeric: tabular-nums;
}
.occupy-card {
  margin-top: 8px;
  padding: 10px 12px;
  background: #fff;
  border-radius: 8px;
  line-height: 1.8;
}
</style>
