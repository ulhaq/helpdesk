<route lang="yaml">
meta:
  layout: bare
  public: true
</route>

<template>
  <p v-if="unavailable" class="p-10 text-center text-sm text-muted-foreground">
    {{ $t('helpCenter.unavailable') }}
  </p>

  <HelpCenterShell v-else :slug="slug" :center="helpCenterStore.center">
    <div v-if="loading" class="space-y-3">
      <Skeleton class="h-8 w-2/3" />
      <Skeleton class="h-48 w-full" />
    </div>

    <p v-else-if="!article" class="text-sm text-muted-foreground">
      {{ $t('helpCenter.articleNotFound') }}
    </p>

    <article v-else class="space-y-6">
      <nav
        :aria-label="$t('helpCenter.breadcrumb')"
        class="flex flex-wrap items-center gap-1 text-sm text-muted-foreground"
      >
        <RouterLink :to="{ name: '/help/[slug]/', params: { slug } }" class="hover:text-foreground">
          {{ $t('helpCenter.title') }}
        </RouterLink>
        <template v-if="article.category">
          <ChevronRight class="h-4 w-4" aria-hidden="true" />
          <RouterLink
            :to="{
              name: '/help/[slug]/',
              params: { slug },
              query: { category: article.category.slug },
            }"
            class="hover:text-foreground"
          >
            {{ article.category.name }}
          </RouterLink>
        </template>
      </nav>

      <header class="space-y-2">
        <h1 class="text-3xl font-semibold tracking-tight">{{ article.title }}</h1>
        <p class="text-sm text-muted-foreground">
          {{ $t('helpCenter.updated', { date: formatDate(article.updated_at) }) }}
        </p>
      </header>

      <MarkdownContent :html="article.html" />
    </article>
  </HelpCenterShell>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'
import { useHead } from '@unhead/vue'
import { ChevronRight } from 'lucide-vue-next'
import { Skeleton } from '@/platform/components/ui/skeleton'
import { useFormatDate } from '@/platform/composables/useFormatDate'
import HelpCenterShell from '@/helpdesk/components/help/HelpCenterShell.vue'
import MarkdownContent from '@/helpdesk/components/kb/MarkdownContent.vue'
import { useHelpCenterStore } from '@/helpdesk/stores/helpCenter'
import type { HelpArticle } from '@/helpdesk/types/kb'

const { t } = useI18n()
const route = useRoute('/help/[slug]/articles/[article]')
const helpCenterStore = useHelpCenterStore()
const { formatDate } = useFormatDate()

const slug = computed(() => route.params.slug)
const loading = ref(true)
const unavailable = ref(false)
const article = ref<HelpArticle | null>(null)

watch(
  [slug, () => route.params.article],
  async ([siteSlug, articleSlug]) => {
    loading.value = true
    try {
      await helpCenterStore.ensureHome(siteSlug)
    } catch {
      unavailable.value = true
      loading.value = false
      return
    }
    unavailable.value = false
    try {
      article.value = await helpCenterStore.article(siteSlug, articleSlug)
    } catch {
      article.value = null
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

const origin = typeof window !== 'undefined' ? window.location.origin : ''

useHead(
  computed(() => ({
    title: article.value
      ? `${article.value.title} · ${helpCenterStore.center?.organization_name ?? t('helpCenter.title')}`
      : t('helpCenter.title'),
    meta: [{ name: 'robots', content: article.value ? 'index, follow' : 'noindex, follow' }],
    link: [
      {
        rel: 'canonical',
        href: `${origin}/help/${slug.value}/articles/${route.params.article}`,
      },
    ],
  })),
)
</script>
