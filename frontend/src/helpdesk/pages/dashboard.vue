<route lang="yaml">
meta:
  layout: dashboard
  requiresAuth: true
  breadcrumb: nav.dashboard
</route>

<template>
  <div class="animate-fade-in space-y-6">
    <PageHeader :title="$t('dashboard.title')" :description="$t('dashboard.description')" />

    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        :label="$t('dashboard.openTickets')"
        :value="canReadTickets ? activeTotal : '-'"
        :icon="Inbox"
        :loading="loading"
        icon-bg="bg-blue-50 dark:bg-blue-950"
        icon-color="text-blue-500"
        :to="canReadTickets ? '/tickets' : undefined"
      />
      <StatCard
        :label="$t('dashboard.myTickets')"
        :value="canReadTickets ? mineTotal : '-'"
        :icon="UserCheck"
        :loading="loading"
        icon-bg="bg-violet-50 dark:bg-violet-950"
        icon-color="text-violet-500"
        :to="canReadTickets ? '/tickets' : undefined"
      />
      <StatCard
        :label="$t('dashboard.plan')"
        :value="planStatusLabel"
        :icon="CreditCard"
        :loading="loading"
        icon-bg="bg-emerald-50 dark:bg-emerald-950"
        icon-color="text-emerald-500"
        :to="hasPermission('manage:subscription') ? '/settings/billing' : undefined"
      />
      <StatCard
        :label="$t('dashboard.notifications')"
        :value="notificationsStore.unreadCount"
        :hint="$t('dashboard.unread')"
        :icon="Bell"
        :loading="loading"
        icon-bg="bg-amber-50 dark:bg-amber-950"
        icon-color="text-amber-500"
        to="/notifications"
      />
    </div>

    <div v-if="canReadTickets" class="rounded-lg border bg-card">
      <div class="flex items-center justify-between px-5 py-4 border-b">
        <h2 class="font-semibold">{{ $t('dashboard.recentTickets') }}</h2>
        <RouterLink
          to="/tickets"
          class="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          {{ $t('dashboard.viewAll') }}
          <ArrowRight class="w-4 h-4" />
        </RouterLink>
      </div>

      <div v-if="loading" class="p-5 space-y-3">
        <Skeleton v-for="n in 3" :key="n" class="h-10 w-full" />
      </div>
      <EmptyState
        v-else-if="recentTickets.length === 0"
        :title="$t('dashboard.emptyTitle')"
        :description="$t('dashboard.emptyDescription')"
        :icon="Inbox"
      >
        <PermissionGuard permission="create:ticket">
          <Button as-child size="sm" class="mt-4">
            <RouterLink to="/tickets">
              <Plus class="w-4 h-4 mr-2" />
              {{ $t('dashboard.emptyCta') }}
            </RouterLink>
          </Button>
        </PermissionGuard>
      </EmptyState>
      <ul v-else class="divide-y">
        <li v-for="ticket in recentTickets" :key="ticket.id">
          <RouterLink
            :to="{ name: '/tickets/[id]', params: { id: ticket.id } }"
            class="flex items-center justify-between gap-4 px-5 py-3 hover:bg-muted/50"
          >
            <div class="min-w-0">
              <p class="text-sm font-medium truncate">
                <span class="text-muted-foreground tabular-nums">#{{ ticket.number }}</span>
                {{ ticket.subject }}
              </p>
              <p class="text-xs text-muted-foreground truncate">{{ ticket.contact.name }}</p>
            </div>
            <div class="flex shrink-0 items-center gap-3">
              <TicketStatusBadge :status="ticket.status" />
              <span class="hidden sm:inline text-xs text-muted-foreground">
                {{ formatRelativeTime(ticket.last_message_at) }}
              </span>
            </div>
          </RouterLink>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { ArrowRight, Bell, CreditCard, Inbox, Plus, UserCheck } from 'lucide-vue-next'
import PageHeader from '@/platform/components/common/PageHeader.vue'
import StatCard from '@/platform/components/common/StatCard.vue'
import EmptyState from '@/platform/components/common/EmptyState.vue'
import PermissionGuard from '@/platform/components/common/PermissionGuard.vue'
import { Button } from '@/platform/components/ui/button'
import { Skeleton } from '@/platform/components/ui/skeleton'
import { useSubscriptionStore } from '@/platform/stores/subscription'
import { useNotificationsStore } from '@/platform/stores/notifications'
import { useProfileStore } from '@/platform/stores/profile'
import { usePermission } from '@/platform/composables/usePermission'
import { useFormatDate } from '@/platform/composables/useFormatDate'
import TicketStatusBadge from '@/helpdesk/components/tickets/TicketStatusBadge.vue'
import { useTicketsStore } from '@/helpdesk/stores/tickets'
import type { TicketOut } from '@/helpdesk/types/ticket'

const ACTIVE_STATUSES = 'open,pending'

const { t, te } = useI18n()
const { hasPermission } = usePermission()
const { formatRelativeTime } = useFormatDate()
const ticketsStore = useTicketsStore()
const subscription = useSubscriptionStore()
const notificationsStore = useNotificationsStore()
const profileStore = useProfileStore()

const loading = ref(true)
const activeTotal = ref(0)
const mineTotal = ref(0)
const recentTickets = ref<TicketOut[]>([])

const canReadTickets = computed(() => hasPermission('read:ticket'))

const planStatusLabel = computed(() => {
  const status = subscription.subscriptionStatus
  if (!status) return '-'
  const key = `subscription.status.${status}`
  return te(key) ? t(key) : status
})

onMounted(async () => {
  try {
    const tasks: Promise<unknown>[] = [subscription.fetchUsage()]
    if (canReadTickets.value) {
      tasks.push(
        ticketsStore
          .list({ page_size: 5, sort: '-last_message_at', status__in: ACTIVE_STATUSES })
          .then((page) => {
            activeTotal.value = page.total
            recentTickets.value = page.items
          }),
      )
      const userId = profileStore.user?.id
      if (userId !== undefined) {
        tasks.push(
          ticketsStore
            .list({ page_size: 5, status__in: ACTIVE_STATUSES, assignee_id__eq: userId })
            .then((page) => {
              mineTotal.value = page.total
            }),
        )
      }
    }
    await Promise.all(tasks)
  } finally {
    loading.value = false
  }
})
</script>
