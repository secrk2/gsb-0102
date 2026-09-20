<template>
  <div class="sidebar">
    <h3>
      楼栋 / 楼层 / 场地
      <button class="link-btn" @click="$emit('add-building')">+ 新楼栋</button>
    </h3>

    <div v-for="b in buildings" :key="b.id" class="building-card">
      <div
        class="building-head"
        :class="{ active: currentBuildingId === b.id && !currentVenueId }"
        @click="$emit('select-building', b.id)"
      >
        <span>
          🏢 {{ b.name }}<span class="code">{{ b.code }}</span>
        </span>
        <span style="display: flex; gap: 2px">
          <button class="icon-btn" title="新增楼层" @click.stop="$emit('add-floor', b)">＋层</button>
        </span>
      </div>

      <template v-if="b.id === currentBuildingId">
        <div v-for="f in groupedByFloor(b)" :key="f.id" class="floor-block">
          <div class="floor-name">
            <span>{{ f.name }}</span>
            <button
              class="icon-btn"
              title="在该层新建场地"
              @click="$emit('add-venue', { building: b, floor: f })"
            >
              ＋
            </button>
          </div>
          <div
            v-for="v in f._venues"
            :key="v.id"
            class="venue-row"
            :class="{ active: currentVenueId === v.id }"
            @click="$emit('select-venue', { building: b, venue: v })"
          >
            <span class="room-no">{{ v.room_no }}</span>
            <span class="vname">{{ v.name }}</span>
            <span class="badge" :class="STATUS_BADGE[v.status]">
              {{ VENUE_STATUSES[v.status] }}
            </span>
          </div>
          <div v-if="!f._venues.length" style="font-size: 11px; color: var(--ink-faint); padding: 2px 8px">
            该层暂无场地
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { VENUE_STATUSES, STATUS_BADGE } from '../constants'

const props = defineProps({
  buildings: { type: Array, required: true },
  venuesByBuilding: { type: Object, default: () => ({}) }, // { [buildingId]: [venue...] }
  currentBuildingId: { type: Number, default: null },
  currentVenueId: { type: Number, default: null },
})
defineEmits([
  'select-building',
  'select-venue',
  'add-building',
  'add-floor',
  'add-venue',
])

function groupedByFloor(building) {
  const venues = props.venuesByBuilding[building.id] || []
  return building.floors
    .slice()
    .sort((a, z) => a.level - z.level)
    .map((f) => ({
      ...f,
      _venues: venues.filter((v) => v.floor_id === f.id),
    }))
}
</script>
