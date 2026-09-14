<route lang="yaml">
meta:
  layout: dashboard
  requiresAuth: true
  permission: manage:kb
  breadcrumb: nav.knowledgeBase
</route>

<template>
  <div class="animate-fade-in">
    <RouterLink
      to="/knowledge-base"
      class="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft class="w-4 h-4" />
      {{ $t('knowledge.backToKb') }}
    </RouterLink>

    <PageHeader :title="$t('knowledge.title')" :description="$t('knowledge.description')">
      <template #actions>
        <Button variant="outline" size="sm" @click="showSearch = true">
          <Search class="w-4 h-4 mr-2" />
          {{ $t('knowledge.search.open') }}
        </Button>
        <Button variant="outline" size="sm" @click="showTextDialog = true">
          <FileText class="w-4 h-4 mr-2" />
          {{ $t('knowledge.addText') }}
        </Button>
        <Button size="sm" :disabled="uploading" @click="fileInput?.click()">
          <Loader2 v-if="uploading" class="w-4 h-4 mr-2 animate-spin" />
          <Upload v-else class="w-4 h-4 mr-2" />
          {{ uploading ? $t('knowledge.uploading') : $t('knowledge.upload') }}
        </Button>
        <input
          ref="fileInput"
          type="file"
          class="hidden"
          :accept="KNOWLEDGE_FILE_TYPES"
          @change="handleUpload"
        />
      </template>
    </PageHeader>

    <p class="mb-4 text-xs text-muted-foreground">{{ $t('knowledge.uploadHint') }}</p>

    <DataTable
      :columns="columns"
      :items="items"
      :total="total"
      :page="pagination.page"
      :page-size="pagination.pageSize"
      :total-pages="totalPages"
      :loading="isLoading"
      :on-row-click="openDocument"
      :row-class="() => 'cursor-pointer'"
      :empty-title="$t('knowledge.emptyTitle')"
      :empty-description="$t('knowledge.emptyDescription')"
      :empty-icon="Lock"
      @sort="setSort"
      @update:page="goToPage"
      @update:page-size="setPageSize"
    >
      <template #toolbar>
        <Input
          v-model="searchQuery"
          :placeholder="$t('knowledge.searchPlaceholder')"
          class="max-w-xs h-9"
          @input="handleSearch"
        />
      </template>
      <template #row="{ item }">
        <TableCell class="font-medium text-sm max-w-md truncate">{{ item.title }}</TableCell>
        <TableCell class="text-sm text-muted-foreground">
          <span class="inline-flex items-center gap-1.5">
            <Paperclip v-if="item.filename" class="h-3.5 w-3.5" aria-hidden="true" />
            <FileText v-else class="h-3.5 w-3.5" aria-hidden="true" />
            {{ item.filename ?? $t('knowledge.pastedText') }}
          </span>
        </TableCell>
        <TableCell class="text-muted-foreground text-xs whitespace-nowrap">
          {{ formatSize(item.size_bytes) }}
        </TableCell>
        <TableCell class="text-muted-foreground text-xs whitespace-nowrap">
          {{ formatRelativeTime(item.updated_at) }}
        </TableCell>
      </template>
    </DataTable>

    <TextDocumentDialog v-model:open="showTextDialog" @created="openDocument" />
    <KnowledgeSearchDialog v-model:open="showSearch" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRouter } from 'vue-router'
import { ArrowLeft, FileText, Loader2, Lock, Paperclip, Search, Upload } from 'lucide-vue-next'
import { Button } from '@/platform/components/ui/button'
import { Input } from '@/platform/components/ui/input'
import { TableCell } from '@/platform/components/ui/table'
import DataTable from '@/platform/components/common/DataTable.vue'
import PageHeader from '@/platform/components/common/PageHeader.vue'
import { useDataTable } from '@/platform/composables/useDataTable'
import { useErrorHandler } from '@/platform/composables/useErrorHandler'
import { useFormatDate } from '@/platform/composables/useFormatDate'
import { useToast } from '@/platform/composables/useToast'
import KnowledgeSearchDialog from '@/helpdesk/components/knowledge/KnowledgeSearchDialog.vue'
import TextDocumentDialog from '@/helpdesk/components/knowledge/TextDocumentDialog.vue'
import { useKnowledgeStore } from '@/helpdesk/stores/knowledge'
import { KNOWLEDGE_FILE_TYPES } from '@/helpdesk/types/knowledge'
import type { KnowledgeDocumentSummary } from '@/helpdesk/types/knowledge'

const { t } = useI18n()
const router = useRouter()
const knowledgeStore = useKnowledgeStore()
const { handleError } = useErrorHandler()
const { toast } = useToast()
const { formatRelativeTime } = useFormatDate()

const columns = [
  { key: 'title', label: t('knowledge.columns.title'), sortable: true },
  { key: 'source', label: t('knowledge.columns.source') },
  { key: 'size_bytes', label: t('knowledge.columns.size') },
  { key: 'updated_at', label: t('knowledge.columns.updated'), sortable: true },
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
} = useDataTable<KnowledgeDocumentSummary>({
  fetcher: (params) =>
    knowledgeStore.listDocuments({ ...params, sort: params.sort ?? '-updated_at' }),
})

const searchQuery = ref('')
let searchTimeout: ReturnType<typeof setTimeout>

function handleSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    setSearch(searchQuery.value || undefined)
  }, 300)
}

function formatSize(bytes: number | null): string {
  if (bytes === null) return '—'
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const showTextDialog = ref(false)
const showSearch = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)

async function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  uploading.value = true
  try {
    const uploaded = await knowledgeStore.uploadDocument(file)
    toast({ title: t('knowledge.uploaded', { title: uploaded.title }) })
    openDocument(uploaded)
  } catch (err: unknown) {
    handleError(err)
  } finally {
    uploading.value = false
  }
}

function openDocument(knowledgeDocument: { id: number }) {
  router.push({ name: '/knowledge-base/internal/[id]', params: { id: knowledgeDocument.id } })
}
</script>
