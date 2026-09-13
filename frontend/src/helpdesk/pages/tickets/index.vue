<route lang="yaml">
meta:
  layout: dashboard
  requiresAuth: true
  permission: read:ticket
  breadcrumb: nav.tickets
</route>

<template>
  <div class="animate-fade-in">
    <PageHeader :title="$t('tickets.title')" :description="$t('tickets.description')">
      <template #actions>
        <PermissionGuard permission="create:ticket">
          <Button size="sm" @click="showForm = true">
            <Plus class="w-4 h-4 mr-2" />
            {{ $t('tickets.create') }}
          </Button>
        </PermissionGuard>
      </template>
    </PageHeader>

    <DataTable
      :columns="columns"
      :items="items"
      :total="total"
      :page="pagination.page"
      :page-size="pagination.pageSize"
      :total-pages="totalPages"
      :loading="isLoading"
      :on-row-click="openTicket"
      :row-class="() => 'cursor-pointer'"
      :empty-title="$t('tickets.emptyTitle')"
      :empty-description="$t('tickets.emptyDescription')"
      :empty-icon="Inbox"
      @sort="setSort"
      @update:page="goToPage"
      @update:page-size="setPageSize"
    >
      <template #toolbar>
        <Input
          v-model="searchQuery"
          :placeholder="$t('tickets.searchPlaceholder')"
          class="max-w-xs h-9"
          @input="handleSearch"
        />
        <Select v-model="statusFilter">
          <SelectTrigger class="w-48 h-9">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="active">{{ $t('tickets.filters.active') }}</SelectItem>
            <SelectItem value="all">{{ $t('tickets.filters.all') }}</SelectItem>
            <SelectItem v-for="s in TICKET_STATUSES" :key="s" :value="s">
              {{ $t(`tickets.status.${s}`) }}
            </SelectItem>
          </SelectContent>
        </Select>
        <Button
          v-if="currentUserId !== null"
          size="sm"
          class="h-9"
          :variant="mineOnly ? 'secondary' : 'outline'"
          :aria-pressed="mineOnly"
          @click="mineOnly = !mineOnly"
        >
          <UserCheck class="w-4 h-4 mr-2" />
          {{ $t('tickets.filters.mine') }}
        </Button>
        <Button
          v-if="contactFilter !== null"
          variant="ghost"
          size="sm"
          class="h-9"
          @click="clearContactFilter"
        >
          {{ $t('tickets.filters.contact') }}
          <X class="w-4 h-4 ml-2" />
        </Button>
      </template>
      <template #row="{ item }">
        <TableCell class="text-muted-foreground text-sm tabular-nums">#{{ item.number }}</TableCell>
        <TableCell class="font-medium text-sm max-w-xs truncate">{{ item.subject }}</TableCell>
        <TableCell class="text-sm">
          <div class="max-w-[12rem] truncate">{{ item.contact.name }}</div>
          <div class="max-w-[12rem] truncate text-xs text-muted-foreground">
            {{ item.contact.email }}
          </div>
        </TableCell>
        <TableCell><TicketStatusBadge :status="item.status" /></TableCell>
        <TableCell><TicketPriorityBadge :priority="item.priority" /></TableCell>
        <TableCell class="text-sm">
          <span v-if="item.assignee">{{ item.assignee.name }}</span>
          <span v-else class="text-muted-foreground">{{ $t('tickets.unassigned') }}</span>
        </TableCell>
        <TableCell class="text-muted-foreground text-xs whitespace-nowrap">
          {{ formatRelativeTime(item.last_message_at) }}
        </TableCell>
      </template>
    </DataTable>

    <TicketForm v-model:open="showForm" @created="openTicket" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { Inbox, Plus, UserCheck, X } from 'lucide-vue-next'
import { Button } from '@/platform/components/ui/button'
import { Input } from '@/platform/components/ui/input'
import { TableCell } from '@/platform/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/platform/components/ui/select'
import PageHeader from '@/platform/components/common/PageHeader.vue'
import DataTable from '@/platform/components/common/DataTable.vue'
import PermissionGuard from '@/platform/components/common/PermissionGuard.vue'
import { useDataTable } from '@/platform/composables/useDataTable'
import { useFormatDate } from '@/platform/composables/useFormatDate'
import { useProfileStore } from '@/platform/stores/profile'
import TicketForm from '@/helpdesk/components/tickets/TicketForm.vue'
import TicketPriorityBadge from '@/helpdesk/components/tickets/TicketPriorityBadge.vue'
import TicketStatusBadge from '@/helpdesk/components/tickets/TicketStatusBadge.vue'
import { useTicketsStore } from '@/helpdesk/stores/tickets'
import { TICKET_STATUSES } from '@/helpdesk/constants'
import type { TicketOut } from '@/helpdesk/types/ticket'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const ticketsStore = useTicketsStore()
const profileStore = useProfileStore()
const { formatRelativeTime } = useFormatDate()

const columns = [
  { key: 'number', label: t('tickets.columns.number'), sortable: true },
  { key: 'subject', label: t('tickets.columns.subject'), sortable: true },
  { key: 'contact', label: t('tickets.columns.contact') },
  { key: 'status', label: t('tickets.columns.status'), sortable: true },
  { key: 'priority', label: t('tickets.columns.priority'), sortable: true },
  { key: 'assignee', label: t('tickets.columns.assignee') },
  { key: 'last_message_at', label: t('tickets.columns.lastActivity'), sortable: true },
]

const {
  items,
  total,
  isLoading,
  totalPages,
  pagination,
  goToPage,
  setPageSize,
  setSort,
  setFilters,
  setSearch,
} = useDataTable<TicketOut>({
  // Most recently active first unless the user picks a column to sort by.
  fetcher: (params) => ticketsStore.list({ ...params, sort: params.sort ?? '-last_message_at' }),
  immediate: false,
})

const currentUserId = computed(() => profileStore.user?.id ?? null)

// 'active' = the working queue (open + pending), 'all' = no status filter.
const statusFilter = ref('active')
const mineOnly = ref(false)
const contactFilter = ref<number | null>(parseId(route.query.contact))

function parseId(value: unknown): number | null {
  const id = Number(value)
  return Number.isInteger(id) && id > 0 ? id : null
}

function statusValues(filter: string): string[] {
  if (filter === 'all') return []
  if (filter === 'active') return ['open', 'pending']
  return [filter]
}

function applyFilters() {
  setFilters([
    { field: 'status', value: statusValues(statusFilter.value), op: 'in' },
    {
      field: 'assignee_id',
      value: mineOnly.value && currentUserId.value !== null ? [currentUserId.value] : [],
      op: 'eq',
    },
    {
      field: 'contact_id',
      value: contactFilter.value !== null ? [contactFilter.value] : [],
      op: 'eq',
    },
  ])
}

watch([statusFilter, mineOnly, contactFilter], applyFilters)
onMounted(applyFilters)

function clearContactFilter() {
  contactFilter.value = null
  const { contact: _contact, ...query } = route.query
  router.replace({ path: '/tickets', query })
}

const searchQuery = ref('')
let searchTimeout: ReturnType<typeof setTimeout>

function handleSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    setSearch(searchQuery.value || undefined)
  }, 300)
}

const showForm = ref(false)

function openTicket(ticket: { id: number }) {
  router.push({ name: '/tickets/[id]', params: { id: ticket.id } })
}
</script>
