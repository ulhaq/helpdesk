<route lang="yaml">
meta:
  layout: dashboard
  requiresAuth: true
  permission: read:contact
  breadcrumb: nav.contacts
</route>

<template>
  <div class="animate-fade-in">
    <PageHeader :title="$t('contacts.title')" :description="$t('contacts.description')">
      <template #actions>
        <PermissionGuard permission="manage:contact">
          <Button size="sm" @click="openCreate">
            <Plus class="w-4 h-4 mr-2" />
            {{ $t('contacts.create') }}
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
      :empty-title="$t('contacts.emptyTitle')"
      :empty-description="$t('contacts.emptyDescription')"
      @sort="setSort"
      @update:page="goToPage"
      @update:page-size="setPageSize"
    >
      <template #toolbar>
        <Input
          v-model="searchQuery"
          :placeholder="$t('contacts.searchPlaceholder')"
          class="max-w-xs h-9"
          @input="handleSearch"
        />
        <Button v-if="searchQuery" variant="ghost" size="sm" @click="clearSearch">
          <X class="w-4 h-4" />
        </Button>
      </template>
      <template #row="{ item }">
        <TableCell class="font-medium text-sm">{{ item.name }}</TableCell>
        <TableCell class="text-muted-foreground text-sm">{{ item.email }}</TableCell>
        <TableCell class="text-muted-foreground text-xs">
          {{ formatDate(item.created_at) }}
        </TableCell>
      </template>
      <template #actions="{ item }">
        <DropdownMenu v-if="hasAnyPermission('read:ticket', 'manage:contact')">
          <DropdownMenuTrigger as-child>
            <Button
              variant="ghost"
              size="sm"
              class="h-7 w-7 p-0"
              :aria-label="$t('common.openMenu')"
            >
              <MoreHorizontal class="w-4 h-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <PermissionGuard permission="read:ticket">
              <DropdownMenuItem class="cursor-pointer" @click="viewTickets(item)">
                <Inbox class="w-4 h-4 mr-2" />
                {{ $t('contacts.viewTickets') }}
              </DropdownMenuItem>
            </PermissionGuard>
            <PermissionGuard permission="manage:contact">
              <DropdownMenuItem class="cursor-pointer" @click="openEdit(item)">
                <Pencil class="w-4 h-4 mr-2" />
                {{ $t('common.edit') }}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                class="cursor-pointer text-destructive focus:text-destructive"
                @click="handleDelete(item)"
              >
                <Trash2 class="w-4 h-4 mr-2" />
                {{ $t('common.delete') }}
              </DropdownMenuItem>
            </PermissionGuard>
          </DropdownMenuContent>
        </DropdownMenu>
      </template>
    </DataTable>

    <ContactForm v-model:open="showForm" :contact="selectedContact" @saved="refresh" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Inbox, MoreHorizontal, Pencil, Plus, Trash2, X } from 'lucide-vue-next'
import { Button } from '@/platform/components/ui/button'
import { Input } from '@/platform/components/ui/input'
import { TableCell } from '@/platform/components/ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/platform/components/ui/dropdown-menu'
import PageHeader from '@/platform/components/common/PageHeader.vue'
import DataTable from '@/platform/components/common/DataTable.vue'
import PermissionGuard from '@/platform/components/common/PermissionGuard.vue'
import { useDataTable } from '@/platform/composables/useDataTable'
import { usePermission } from '@/platform/composables/usePermission'
import { useConfirm } from '@/platform/composables/useConfirm'
import { useToast } from '@/platform/composables/useToast'
import { useErrorHandler } from '@/platform/composables/useErrorHandler'
import { useFormatDate } from '@/platform/composables/useFormatDate'
import ContactForm from '@/helpdesk/components/contacts/ContactForm.vue'
import { useContactsStore } from '@/helpdesk/stores/contacts'
import type { ContactOut } from '@/helpdesk/types/contact'

const { t } = useI18n()
const router = useRouter()
const contactsStore = useContactsStore()
const { formatDate } = useFormatDate()
const { toast } = useToast()
const { handleError } = useErrorHandler()
const { confirm } = useConfirm()
const { hasAnyPermission } = usePermission()

const columns = [
  { key: 'name', label: t('contacts.columns.name'), sortable: true },
  { key: 'email', label: t('contacts.columns.email'), sortable: true },
  { key: 'created_at', label: t('contacts.columns.created'), sortable: true },
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
  setSearch,
  refresh,
} = useDataTable<ContactOut>({ fetcher: contactsStore.list })

const searchQuery = ref('')
let searchTimeout: ReturnType<typeof setTimeout>

function handleSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    setSearch(searchQuery.value || undefined)
  }, 300)
}

function clearSearch() {
  searchQuery.value = ''
  setSearch(undefined)
}

const showForm = ref(false)
const selectedContact = ref<ContactOut | null>(null)

function openCreate() {
  selectedContact.value = null
  showForm.value = true
}

function openEdit(contact: ContactOut) {
  selectedContact.value = contact
  showForm.value = true
}

function viewTickets(contact: ContactOut) {
  router.push({ path: '/tickets', query: { contact: String(contact.id) } })
}

async function handleDelete(contact: ContactOut) {
  const ok = await confirm(
    t('contacts.deleteTitle'),
    t('contacts.deleteDescription', { name: contact.name }),
    t('common.delete'),
  )
  if (!ok) return
  try {
    await contactsStore.remove(contact.id)
    toast({ title: t('contacts.deleted') })
    refresh()
  } catch (err: unknown) {
    handleError(err, t('contacts.deleteFailed'))
  }
}
</script>
