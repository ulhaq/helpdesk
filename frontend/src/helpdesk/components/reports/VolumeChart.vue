<template>
  <div class="hd-viz space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <ul class="flex flex-wrap gap-4 text-sm text-muted-foreground">
        <li v-for="line in series" :key="line.key" class="flex items-center gap-2">
          <span
            class="h-0.5 w-4 rounded-full"
            :style="{ background: line.color }"
            aria-hidden="true"
          />
          {{ line.label }}
        </li>
      </ul>
      <Button variant="ghost" size="sm" @click="showTable = !showTable">
        {{ showTable ? $t('reports.hideTable') : $t('reports.showTable') }}
      </Button>
    </div>

    <div v-show="!showTable" ref="container" class="relative">
      <svg
        :width="width"
        :height="HEIGHT"
        role="img"
        tabindex="0"
        :aria-label="ariaLabel"
        class="block rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
        @pointermove="onPointer"
        @pointerleave="active = null"
        @keydown="onKey"
        @blur="active = null"
      >
        <g aria-hidden="true">
          <template v-for="tick in yTicks" :key="tick">
            <line
              :x1="PAD.left"
              :x2="width - PAD.right"
              :y1="y(tick)"
              :y2="y(tick)"
              stroke="var(--hd-viz-grid)"
              stroke-width="1"
              shape-rendering="crispEdges"
            />
            <text
              :x="PAD.left - 8"
              :y="y(tick)"
              text-anchor="end"
              dominant-baseline="middle"
              class="hd-viz-tick"
            >
              {{ numberFormat.format(tick) }}
            </text>
          </template>
          <text
            v-for="(index, position) in xTickIndexes"
            :key="`x${index}`"
            :x="x(index)"
            :y="HEIGHT - 8"
            :text-anchor="
              position === 0 ? 'start' : position === xTickIndexes.length - 1 ? 'end' : 'middle'
            "
            class="hd-viz-tick"
          >
            {{ formatDay(points[index]?.day ?? '') }}
          </text>

          <line
            v-if="active !== null"
            :x1="x(active)"
            :x2="x(active)"
            :y1="PAD.top"
            :y2="HEIGHT - PAD.bottom"
            stroke="var(--hd-viz-axis)"
            stroke-width="1"
            shape-rendering="crispEdges"
          />

          <path
            v-for="line in series"
            :key="line.key"
            :d="linePath(line.key)"
            fill="none"
            :stroke="line.color"
            stroke-width="2"
            stroke-linejoin="round"
            stroke-linecap="round"
          />

          <template v-for="line in series" :key="`dot${line.key}`">
            <circle
              v-if="markerIndex !== null"
              :cx="x(markerIndex)"
              :cy="y(points[markerIndex]?.[line.key] ?? 0)"
              r="4"
              :fill="line.color"
              stroke="var(--hd-viz-surface)"
              stroke-width="2"
            />
          </template>
        </g>
      </svg>

      <div
        v-if="activePoint"
        role="status"
        class="pointer-events-none absolute z-10 min-w-36 rounded-md border bg-popover px-3 py-2 text-xs shadow-md"
        :style="tooltipStyle"
      >
        <p class="mb-1 text-muted-foreground">{{ formatDay(activePoint.day) }}</p>
        <p v-for="line in series" :key="line.key" class="flex items-center gap-2">
          <span
            class="h-0.5 w-3 rounded-full"
            :style="{ background: line.color }"
            aria-hidden="true"
          />
          <span class="font-semibold tabular-nums text-foreground">
            {{ numberFormat.format(activePoint[line.key]) }}
          </span>
          <span class="text-muted-foreground">{{ line.label }}</span>
        </p>
      </div>
    </div>

    <div v-if="showTable" class="max-h-72 overflow-auto rounded-md border">
      <table class="w-full text-sm">
        <thead class="sticky top-0 bg-muted">
          <tr>
            <th scope="col" class="px-3 py-2 text-left font-medium">
              {{ $t('reports.columns.day') }}
            </th>
            <th
              v-for="line in series"
              :key="line.key"
              scope="col"
              class="px-3 py-2 text-right font-medium"
            >
              {{ line.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="point in points" :key="point.day" class="border-t">
            <td class="px-3 py-1.5 text-muted-foreground">{{ formatDay(point.day) }}</td>
            <td v-for="line in series" :key="line.key" class="px-3 py-1.5 text-right tabular-nums">
              {{ numberFormat.format(point[line.key]) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/platform/components/ui/button'
import type { DailyVolume } from '@/helpdesk/types/reports'

type SeriesKey = 'created' | 'resolved'

const props = defineProps<{ points: DailyVolume[] }>()

const HEIGHT = 240
const PAD = { top: 12, right: 16, bottom: 28, left: 40 }

const { t, locale } = useI18n()

const series = computed(() => [
  { key: 'created' as SeriesKey, label: t('reports.created'), color: 'var(--hd-viz-series-1)' },
  { key: 'resolved' as SeriesKey, label: t('reports.resolved'), color: 'var(--hd-viz-series-2)' },
])

const container = ref<HTMLElement | null>(null)
const width = ref(640)
let observer: ResizeObserver | null = null

onMounted(() => {
  if (!container.value) return
  observer = new ResizeObserver(([entry]) => {
    if (entry && entry.contentRect.width > 0) width.value = Math.max(280, entry.contentRect.width)
  })
  observer.observe(container.value)
})
onBeforeUnmount(() => observer?.disconnect())

const numberFormat = computed(() => new Intl.NumberFormat(locale.value))
const dayFormat = computed(
  () => new Intl.DateTimeFormat(locale.value, { day: 'numeric', month: 'short', timeZone: 'UTC' }),
)
const formatDay = (iso: string) => (iso ? dayFormat.value.format(new Date(`${iso}T00:00:00Z`)) : '')

/** Round axis ticks (1/2/5 × 10^k steps), about four intervals. */
function niceTicks(max: number): number[] {
  if (max <= 0) return [0, 1]
  const rough = max / 4
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const stepSize = Math.max(
    1,
    [1, 2, 5, 10].map((m) => m * magnitude).find((candidate) => candidate >= rough) ??
      magnitude * 10,
  )
  const top = Math.ceil(max / stepSize) * stepSize
  return Array.from({ length: Math.round(top / stepSize) + 1 }, (_, i) => i * stepSize)
}

const yTicks = computed(() =>
  niceTicks(Math.max(0, ...props.points.flatMap((point) => [point.created, point.resolved]))),
)
const yMax = computed(() => yTicks.value[yTicks.value.length - 1] || 1)
const plotWidth = computed(() => width.value - PAD.left - PAD.right)
const plotHeight = HEIGHT - PAD.top - PAD.bottom
const lastIndex = computed(() => Math.max(0, props.points.length - 1))
const step = computed(() => (lastIndex.value > 0 ? plotWidth.value / lastIndex.value : 0))

const x = (index: number) => PAD.left + index * step.value
const y = (value: number) => PAD.top + plotHeight - (value / yMax.value) * plotHeight

function linePath(key: SeriesKey): string {
  return props.points
    .map((point, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(point[key]).toFixed(1)}`)
    .join('')
}

const xTickIndexes = computed(() => {
  const count = Math.min(props.points.length, Math.max(2, Math.floor(plotWidth.value / 110)))
  const indexes = new Set<number>()
  for (let k = 0; k < count; k++) {
    indexes.add(Math.round((k * lastIndex.value) / Math.max(1, count - 1)))
  }
  return [...indexes]
})

// Hover / keyboard crosshair: snaps to the nearest day.
const active = ref<number | null>(null)
const activePoint = computed(() => (active.value === null ? null : props.points[active.value]))
// Without an active day the markers sit on the latest one.
const markerIndex = computed(() => (props.points.length ? (active.value ?? lastIndex.value) : null))

function onPointer(event: PointerEvent) {
  if (!props.points.length) return
  const rect = (event.currentTarget as SVGSVGElement).getBoundingClientRect()
  const index = Math.round((event.clientX - rect.left - PAD.left) / (step.value || 1))
  active.value = Math.min(lastIndex.value, Math.max(0, index))
}

function onKey(event: KeyboardEvent) {
  if (!props.points.length) return
  const current = active.value ?? lastIndex.value
  const next: Record<string, number> = {
    ArrowLeft: current - 1,
    ArrowRight: current + 1,
    Home: 0,
    End: lastIndex.value,
  }
  if (event.key === 'Escape') {
    active.value = null
  } else if (event.key in next) {
    event.preventDefault()
    active.value = Math.min(lastIndex.value, Math.max(0, next[event.key] ?? current))
  }
}

const tooltipStyle = computed(() => {
  if (active.value === null) return {}
  const left = x(active.value)
  return left > width.value - 180
    ? { top: `${PAD.top}px`, right: `${width.value - left + 12}px` }
    : { top: `${PAD.top}px`, left: `${left + 12}px` }
})

const ariaLabel = computed(() => {
  const created = props.points.reduce((sum, point) => sum + point.created, 0)
  const resolved = props.points.reduce((sum, point) => sum + point.resolved, 0)
  return `${t('reports.volumeTitle')}: ${t('reports.created')} ${created}, ${t('reports.resolved')} ${resolved}`
})

const showTable = ref(false)
</script>
