<template>
  <ul class="hd-viz space-y-3">
    <!-- Label above the bar: category names never get truncated. -->
    <li v-for="row in rows" :key="row.key" class="space-y-1 text-sm">
      <span class="block text-muted-foreground">{{ row.label }}</span>
      <div
        class="relative flex min-w-0 items-center gap-2 rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
        tabindex="0"
        :aria-label="`${row.label}: ${row.count} (${row.share}%)`"
        @pointerenter="hovered = row.key"
        @pointerleave="hovered = null"
        @focus="hovered = row.key"
        @blur="hovered = null"
      >
        <div
          class="hd-viz-bar h-3 shrink-0"
          :style="{
            width: `${row.width}%`,
            opacity: hovered !== null && hovered !== row.key ? 0.5 : 1,
          }"
          aria-hidden="true"
        />
        <span class="text-xs font-medium tabular-nums text-foreground">
          {{ numberFormat.format(row.count) }}
        </span>
        <div
          v-if="hovered === row.key"
          role="status"
          class="pointer-events-none absolute bottom-full left-0 z-10 mb-1 whitespace-nowrap rounded-md border bg-popover px-2 py-1 text-xs shadow-md"
        >
          <span class="font-semibold text-foreground">{{ row.share }}%</span>
          <span class="ml-1 text-muted-foreground">{{ row.label }}</span>
        </div>
      </div>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ items: { key: string; label: string; count: number }[] }>()

const { locale } = useI18n()
const numberFormat = computed(() => new Intl.NumberFormat(locale.value))
const hovered = ref<string | null>(null)

// Bars scale to the largest value and stop short of full width so the value
// label always fits beside the bar end.
const MAX_BAR_WIDTH = 85

const rows = computed(() => {
  const max = Math.max(0, ...props.items.map((item) => item.count))
  const total = props.items.reduce((sum, item) => sum + item.count, 0)
  return props.items.map((item) => ({
    ...item,
    width: max ? (item.count / max) * MAX_BAR_WIDTH : 0,
    share: total ? Math.round((item.count / total) * 100) : 0,
  }))
})
</script>
