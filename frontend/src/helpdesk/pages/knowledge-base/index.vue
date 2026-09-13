<route lang="yaml">
meta:
  layout: dashboard
  requiresAuth: true
  permission: manage:kb
  breadcrumb: nav.knowledgeBase
</route>

<template>
  <div class="animate-fade-in">
    <PageHeader :title="$t('kb.title')" :description="$t('kb.description')">
      <template #title-suffix>
        <PlanQuota :count="total" :limit="articleLimit" variant="bar" />
      </template>
      <template #actions>
        <Button variant="outline" size="sm" @click="showCategories = true">
          <FolderTree class="w-4 h-4 mr-2" />
          {{ $t('kb.manageCategories') }}
        </Button>
        <Button size="sm" as-child>
          <RouterLink to="/knowledge-base/articles/new">
            <Plus class="w-4 h-4 mr-2" />
            {{ $t('kb.create') }}
          </RouterLink>
        </Button>
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
      :on-row-click="openArticle"
      :row-class="() => 'cursor-pointer'"
      :empty-title="$t('kb.emptyTitle')"
      :empty-description="$t('kb.emptyDescription')"
      :empty-icon="BookOpen"
      @sort="setSort"
      @update:page="goToPage"
      @update:page-size="setPageSize"
    >
      <template #toolbar>
        <Input
          v-model="searchQuery"
          :placeholder="$t('kb.searchPlaceholder')"
          class="max-w-xs h-9"
          @input="handleSearch"
        />
        <Select v-model="statusFilter">
          <SelectTrigger class="w-40 h-9">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem :value="ALL">{{ $t('kb.filters.allStatuses') }}</SelectItem>
            <SelectItem value="published">{{ $t('kb.status.published') }}</SelectItem>
            <SelectItem value="draft">{{ $t('kb.status.draft') }}</SelectItem>
          </SelectContent>
        </Select>
        <Select v-if="kbStore.categories.length" v-model="categoryFilter">
          <SelectTrigger class="w-48 h-9">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem :value="ALL">{{ $t('kb.filters.allCategories') }}</SelectItem>
            <SelectItem
              v-for="category in kbStore.categories"
              :key="category.id"
              :value="String(category.id)"
            >
              {{ category.name }}
            </SelectItem>
          </SelectContent>
        </Select>
      </template>
      <template #row="{ item }">
        <TableCell class="font-medium text-sm max-w-md truncate">{{ item.title }}</TableCell>
        <TableCell class="text-sm">
          <span v-if="item.category">{{ item.category.name }}</span>
          <span v-else class="text-muted-foreground">{{ $t('kb.uncategorized') }}</span>
        </TableCell>
        <TableCell><ArticleStatusBadge :status="item.status" /></TableCell>
        <TableCell class="text-muted-foreground text-xs whitespace-nowrap">
          {{ formatRelativeTime(item.updated_at) }}
        </TableCell>
      </template>
    </DataTable>

    <CategoryManager v-model:open="showCategories" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRouter } from 'vue-router'
import { BookOpen, FolderTree, Plus } from 'lucide-vue-next'
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
import DataTable from '@/platform/components/common/DataTable.vue'
import PageHeader from '@/platform/components/common/PageHeader.vue'
import PlanQuota from '@/platform/components/common/PlanQuota.vue'
import { useDataTable } from '@/platform/composables/useDataTable'
import { useFormatDate } from '@/platform/composables/useFormatDate'
import { useSubscriptionStore } from '@/platform/stores/subscription'
import ArticleStatusBadge from '@/helpdesk/components/kb/ArticleStatusBadge.vue'
import CategoryManager from '@/helpdesk/components/kb/CategoryManager.vue'
import { HelpdeskUsageMetric } from '@/helpdesk/constants'
import { useKbStore } from '@/helpdesk/stores/kb'
import type { KbArticleSummary } from '@/helpdesk/types/kb'

const ALL = '__all__'

const { t } = useI18n()
const router = useRouter()
const kbStore = useKbStore()
const subscriptionStore = useSubscriptionStore()
const { formatRelativeTime } = useFormatDate()

const columns = [
  { key: 'title', label: t('kb.columns.title'), sortable: true },
  { key: 'category', label: t('kb.columns.category') },
  { key: 'status', label: t('kb.columns.status'), sortable: true },
  { key: 'updated_at', label: t('kb.columns.updated'), sortable: true },
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
} = useDataTable<KbArticleSummary>({
  fetcher: (params) => kbStore.listArticles({ ...params, sort: params.sort ?? '-updated_at' }),
})

const articleLimit = computed(() => subscriptionStore.limitFor(HelpdeskUsageMetric.KB_ARTICLES))

const statusFilter = ref(ALL)
const categoryFilter = ref(ALL)

watch([statusFilter, categoryFilter], () => {
  setFilters([
    { field: 'status', value: statusFilter.value === ALL ? [] : [statusFilter.value], op: 'eq' },
    {
      field: 'category_id',
      value: categoryFilter.value === ALL ? [] : [Number(categoryFilter.value)],
      op: 'eq',
    },
  ])
})

onMounted(() => {
  subscriptionStore.fetchUsage()
  kbStore.loadCategories().catch(() => undefined)
})

const searchQuery = ref('')
let searchTimeout: ReturnType<typeof setTimeout>

function handleSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    setSearch(searchQuery.value || undefined)
  }, 300)
}

const showCategories = ref(false)

function openArticle(article: KbArticleSummary) {
  router.push({ name: '/knowledge-base/articles/[id]', params: { id: article.id } })
}
</script>
