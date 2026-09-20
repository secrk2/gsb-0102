<script setup>
import { onMounted } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useBuildings } from './buildings-store'

const { state, loadBuildings, setBuilding } = useBuildings()

onMounted(loadBuildings)
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <span class="logo">汇</span>
        <div>
          <div class="brand-name">汇堂</div>
          <div class="brand-sub">园区场地档期平台</div>
        </div>
      </div>

      <nav class="nav">
        <RouterLink to="/schedule" class="nav-link">档期与占用</RouterLink>
        <RouterLink to="/venues" class="nav-link">场地档案</RouterLink>
      </nav>

      <div class="building-box">
        <span class="building-label">楼栋</span>
        <select
          class="select"
          :value="state.buildingId ?? ''"
          @change="setBuilding(Number($event.target.value))"
        >
          <option v-for="b in state.buildings" :key="b.id" :value="b.id">
            {{ b.name }}
          </option>
        </select>
      </div>
    </header>

    <div v-if="state.loadError" class="top-error">
      楼栋列表加载失败：{{ state.loadError }}，请确认后端服务已启动后
      <a @click="loadBuildings">重试</a>。
    </div>

    <main class="content">
      <RouterView :key="state.buildingId" />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
}
.topbar {
  height: 60px;
  background: #fff;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 24px;
  gap: 36px;
  position: sticky;
  top: 0;
  z-index: 20;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.logo {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: linear-gradient(135deg, #2f54eb, #722ed1);
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.brand-name {
  font-size: 17px;
  font-weight: 700;
  line-height: 1.2;
}
.brand-sub {
  font-size: 11px;
  color: var(--text-3);
}
.nav {
  display: flex;
  gap: 4px;
}
.nav-link {
  padding: 8px 16px;
  border-radius: 8px;
  color: var(--text-2);
  font-size: 14px;
}
.nav-link.router-link-active {
  background: #eef3ff;
  color: var(--brand);
  font-weight: 600;
}
.building-box {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}
.building-label {
  color: var(--text-3);
  font-size: 13px;
}
.top-error {
  background: var(--danger-bg);
  color: var(--danger);
  padding: 8px 24px;
  font-size: 13px;
}
.content {
  padding: 20px 24px 40px;
  max-width: 1500px;
  margin: 0 auto;
}
</style>
