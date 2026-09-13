<route lang="yaml">
meta:
  layout: dashboard
  requiresAuth: true
  permission: read:report
  breadcrumb: nav.reports
</route>

<template>
  <div class="animate-fade-in space-y-6">
    <PageHeader :title="$t('reports.title')" :description="$t('reports.description')" />

    <!-- One filter row, above everything it scopes. -->
    <div
      class="flex flex-wrap items-center gap-1"
      role="group"
      :aria-label="$t('reports.periodLabel')"
    >
      <Button
        v-for="period in PERIODS"
        :key="period"
        size="sm"
        :variant="days === period ? 'secondary' : 'ghost'"
        :aria-pressed="days === period"
        @click="days = period"
      >
        {{ $t(`reports.period.d${period}`) }}
      </Button>
    </div>

    <div v-if="!summary" class="space-y-4">
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
        <Skeleton v-for="n in 5" :key="n" class="h-24 w-full" />
      </div>
      <Skeleton class="h-72 w-full" />
    </div>

    <!-- While a new period loads, the previous numbers stay, dimmed. -->
    <div
      v-else
      :class="cn('space-y-6 transition-opacity', loading && 'opacity-60')"
      :aria-busy="loading"
    >
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
        <StatCard
          :label="$t('reports.created')"
          :value="numberFormat.format(summary.created)"
          :icon="Inbox"
          icon-bg="bg-blue-50 dark:bg-blue-950"
          icon-color="text-blue-500"
        />
        <StatCard
          :label="$t('reports.resolved')"
          :value="numberFormat.format(summary.resolved)"
          :icon="CheckCircle2"
          icon-bg="bg-emerald-50 dark:bg-emerald-950"
          icon-color="text-emerald-500"
        />
        <StatCard
          :label="$t('reports.backlog')"
          :value="numberFormat.format(summary.backlog)"
          :hint="$t('reports.backlogHint', { count: summary.unassigned_backlog })"
          :icon="Layers"
          icon-bg="bg-amber-50 dark:bg-amber-950"
          icon-color="text-amber-500"
          to="/tickets"
        />
        <StatCard
          :label="$t('reports.firstResponse')"
          :value="formatDuration(summary.first_response.median_seconds)"
          :hint="$t('reports.basedOn', summary.first_response.sample_size)"
          :icon="Timer"
          icon-bg="bg-violet-50 dark:bg-violet-950"
          icon-color="text-violet-500"
        />
        <StatCard
          :label="$t('reports.resolution')"
          :value="formatDuration(summary.resolution.median_seconds)"
          :hint="$t('reports.basedOn', summary.resolution.sample_size)"
          :icon="Hourglass"
          icon-bg="bg-sky-50 dark:bg-sky-950"
          icon-color="text-sky-500"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle class="text-base">{{ $t('reports.volumeTitle') }}</CardTitle>
          <CardDescription>{{ $t('reports.volumeDescription') }}</CardDescription>
        </CardHeader>
        <CardContent>
          <VolumeChart v-if="hasVolume" :points="summary.daily" />
          <p v-else class="py-10 text-center text-sm text-muted-foreground">
            {{ $t('reports.empty') }}
          </p>
        </CardContent>
      </Card>

      <div class="grid gap-4 lg:grid-cols-3">
        <Card v-for="breakdown in breakdowns" :key="breakdown.title">
          <CardHeader>
            <CardTitle class="text-base">{{ breakdown.title }}</CardTitle>
            <CardDescription>{{ $t('reports.breakdownHint') }}</CardDescription>
          </CardHeader>
          <CardContent>
            <BreakdownBars :items="breakdown.items" />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle class="text-base">{{ $t('reports.agentsTitle') }}</CardTitle>
        </CardHeader>
        <CardContent>
          <p v-if="!summary.agents.length" class="text-sm text-muted-foreground">
            {{ $t('reports.agentsEmpty') }}
          </p>
          <Table v-else>
            <TableHeader>
              <TableRow>
                <TableHead>{{ $t('reports.columns.agent') }}</TableHead>
                <TableHead class="text-right">{{ $t('reports.columns.open') }}</TableHead>
                <TableHead class="text-right">{{ $t('reports.columns.resolved') }}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="agent in summary.agents" :key="agent.user_id">
                <TableCell class="font-medium">{{ agent.name }}</TableCell>
                <TableCell class="text-right tabular-nums">
                  {{ numberFormat.format(agent.open) }}
                </TableCell>
                <TableCell class="text-right tabular-nums">
                  {{ numberFormat.format(agent.resolved) }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { CheckCircle2, Hourglass, Inbox, Layers, Timer } from 'lucide-vue-next'
import { Button } from '@/platform/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/platform/components/ui/card'
import { Skeleton } from '@/platform/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/platform/components/ui/table'
import PageHeader from '@/platform/components/common/PageHeader.vue'
import StatCard from '@/platform/components/common/StatCard.vue'
import { cn } from '@/platform/lib/utils'
import { useErrorHandler } from '@/platform/composables/useErrorHandler'
import BreakdownBars from '@/helpdesk/components/reports/BreakdownBars.vue'
import VolumeChart from '@/helpdesk/components/reports/VolumeChart.vue'
import { useReportsStore } from '@/helpdesk/stores/reports'
import type { CountByKey } from '@/helpdesk/types/reports'
import '@/helpdesk/styles/charts.css'

const PERIODS = [7, 30, 90] as const

const { t, locale } = useI18n()
const { handleError } = useErrorHandler()
const reportsStore = useReportsStore()

const days = ref<number>(30)
const loading = ref(false)
const summary = computed(() => reportsStore.summary)

async function load() {
  loading.value = true
  try {
    await reportsStore.load(days.value)
  } catch (err: unknown) {
    handleError(err)
  } finally {
    loading.value = false
  }
}

watch(days, load, { immediate: true })

const numberFormat = computed(() => new Intl.NumberFormat(locale.value))

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '-'
  const format = new Intl.NumberFormat(locale.value, { maximumFractionDigits: 1 })
  if (seconds < 3600) {
    return t('reports.duration.minutes', {
      n: format.format(Math.max(1, Math.round(seconds / 60))),
    })
  }
  if (seconds < 48 * 3600) {
    return t('reports.duration.hours', { n: format.format(seconds / 3600) })
  }
  return t('reports.duration.days', { n: format.format(seconds / 86400) })
}

const hasVolume = computed(
  () => summary.value?.daily.some((day) => day.created > 0 || day.resolved > 0) ?? false,
)

function labelled(items: CountByKey[], namespace: string) {
  return items.map((item) => ({ ...item, label: t(`${namespace}.${item.key}`) }))
}

const breakdowns = computed(() => {
  const current = summary.value
  if (!current) return []
  return [
    { title: t('reports.breakdownStatus'), items: labelled(current.by_status, 'tickets.status') },
    {
      title: t('reports.breakdownChannel'),
      items: labelled(current.by_channel, 'tickets.channel'),
    },
    {
      title: t('reports.breakdownPriority'),
      items: labelled(current.by_priority, 'tickets.priority'),
    },
  ]
})
</script>
