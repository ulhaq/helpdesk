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
      {{ $t('kb.editor.back') }}
    </RouterLink>

    <Skeleton v-if="loading" class="h-96 w-full" />

    <EmptyState
      v-else-if="!article"
      :title="$t('kb.editor.notFoundTitle')"
      :description="$t('kb.editor.notFoundDescription')"
      :icon="BookOpen"
    />

    <template v-else>
      <PageHeader :title="$t('kb.editor.editTitle')">
        <template #actions>
          <Button variant="outline" size="sm" @click="handleDelete">
            <Trash2 class="w-4 h-4 mr-2" />
            {{ $t('common.delete') }}
          </Button>
        </template>
      </PageHeader>
      <ArticleEditor :article="article" @saved="article = $event" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ArrowLeft, BookOpen, Trash2 } from 'lucide-vue-next'
import { Button } from '@/platform/components/ui/button'
import { Skeleton } from '@/platform/components/ui/skeleton'
import EmptyState from '@/platform/components/common/EmptyState.vue'
import PageHeader from '@/platform/components/common/PageHeader.vue'
import { useConfirm } from '@/platform/composables/useConfirm'
import { useErrorHandler } from '@/platform/composables/useErrorHandler'
import { useToast } from '@/platform/composables/useToast'
import ArticleEditor from '@/helpdesk/components/kb/ArticleEditor.vue'
import { useKbStore } from '@/helpdesk/stores/kb'
import type { KbArticle } from '@/helpdesk/types/kb'

const { t } = useI18n()
const route = useRoute('/knowledge-base/articles/[id]')
const router = useRouter()
const kbStore = useKbStore()
const { confirm } = useConfirm()
const { handleError } = useErrorHandler()
const { toast } = useToast()

const article = ref<KbArticle | null>(null)
const loading = ref(true)

watch(
  () => route.params.id,
  async (id) => {
    loading.value = true
    try {
      article.value = await kbStore.getArticle(Number(id))
    } catch {
      article.value = null
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

async function handleDelete() {
  if (!article.value) return
  const ok = await confirm(
    t('kb.deleteTitle'),
    t('kb.deleteDescription', { title: article.value.title }),
    t('common.delete'),
  )
  if (!ok) return
  try {
    await kbStore.removeArticle(article.value.id)
    toast({ title: t('kb.deleted') })
    router.push('/knowledge-base')
  } catch (err: unknown) {
    handleError(err, t('kb.deleteFailed'))
  }
}
</script>
