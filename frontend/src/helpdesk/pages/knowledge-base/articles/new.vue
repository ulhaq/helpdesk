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
    <PageHeader :title="$t('kb.editor.newTitle')" />
    <ArticleEditor @saved="openSaved" />
  </div>
</template>

<script setup lang="ts">
import { RouterLink, useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'
import PageHeader from '@/platform/components/common/PageHeader.vue'
import ArticleEditor from '@/helpdesk/components/kb/ArticleEditor.vue'
import type { KbArticle } from '@/helpdesk/types/kb'

const router = useRouter()

function openSaved(article: KbArticle) {
  router.replace({ name: '/knowledge-base/articles/[id]', params: { id: article.id } })
}
</script>
