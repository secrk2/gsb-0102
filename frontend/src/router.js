import { createRouter, createWebHistory } from 'vue-router'
import VenuesView from './views/VenuesView.vue'
import ScheduleView from './views/ScheduleView.vue'

const routes = [
  { path: '/', redirect: '/schedule' },
  { path: '/venues', name: 'venues', component: VenuesView },
  { path: '/schedule', name: 'schedule', component: ScheduleView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
