<route lang="yaml">
meta:
  layout: bare
  public: true
</route>

<template>
  <p v-if="unavailable" class="p-10 text-center text-sm text-muted-foreground">
    {{ $t('helpCenter.unavailable') }}
  </p>

  <HelpCenterShell
    v-else
    :slug="slug"
    :center="helpCenterStore.center"
    :initial-query="searchQuery"
  >
    <div v-if="loading" class="space-y-3">
      <Skeleton v-for="n in 4" :key="n" class="h-16 w-full" />
    </div>

    <section v-else-if="results" class="space-y-4">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h1 class="text-xl font-semibold">
          {{
            results.category
              ? results.category.name
              : $t('helpCenter.resultsFor', { query: searchQuery })
          }}
        </h1>
        <RouterLink
          :to="{ name: '/help/[slug]/', params: { slug } }"
          class="text-sm text-muted-foreground hover:text-foreground"
        >
          {{ $t('helpCenter.allArticles') }}
        </RouterLink>
      </div>
      <HelpArticleList
        :slug="slug"
        :articles="results.articles"
        :empty-text="$t('helpCenter.noResults')"
      />
    </section>

    <template v-else-if="helpCenterStore.center">
      <section v-if="helpCenterStore.center.categories.length" class="mb-10 space-y-4">
        <h2 class="text-lg font-semibold">{{ $t('helpCenter.categories') }}</h2>
        <ul class="grid gap-3 sm:grid-cols-2">
          <li v-for="category in helpCenterStore.center.categories" :key="category.slug">
            <RouterLink
              :to="{ name: '/help/[slug]/', params: { slug }, query: { category: category.slug } }"
              class="block h-full rounded-lg border p-4 transition-colors hover:bg-muted/50"
            >
              <p class="font-medium">{{ category.name }}</p>
              <p v-if="category.description" class="mt-1 text-sm text-muted-foreground">
                {{ category.description }}
              </p>
              <p class="mt-2 text-xs text-muted-foreground">
                {{ $t('helpCenter.articleCount', category.article_count) }}
              </p>
            </RouterLink>
          </li>
        </ul>
      </section>

      <section class="space-y-4">
        <h2 class="text-lg font-semibold">{{ $t('helpCenter.recent') }}</h2>
        <HelpArticleList
          :slug="slug"
          :articles="helpCenterStore.center.recent_articles"
          :empty-text="$t('helpCenter.noArticles')"
        />
      </section>
    </template>
  </HelpCenterShell>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'
import { useHead } from '@unhead/vue'
import { Skeleton } from '@/platform/components/ui/skeleton'
import HelpArticleList from '@/helpdesk/components/help/HelpArticleList.vue'
import HelpCenterShell from '@/helpdesk/components/help/HelpCenterShell.vue'
import { useHelpCenterStore } from '@/helpdesk/stores/helpCenter'
import type { HelpSearch } from '@/helpdesk/types/kb'

const { t } = useI18n()
const route = useRoute('/help/[slug]/')
const helpCenterStore = useHelpCenterStore()

const slug = computed(() => route.params.slug)
const searchQuery = computed(() => (typeof route.query.q === 'string' ? route.query.q : ''))
const categorySlug = computed(() =>
  typeof route.query.category === 'string' ? route.query.category : '',
)

const loading = ref(true)
const unavailable = ref(false)
const results = ref<HelpSearch | null>(null)

async function load() {
  loading.value = true
  try {
    await helpCenterStore.ensureHome(slug.value)
    unavailable.value = false
    results.value =
      searchQuery.value || categorySlug.value
        ? await helpCenterStore.search(slug.value, {
            q: searchQuery.value || undefined,
            category: categorySlug.value || undefined,
          })
        : null
  } catch {
    // Without the help center itself there is nothing to show; a bad category
    // link just finds no articles.
    if (helpCenterStore.center) results.value = { category: null, articles: [] }
    else unavailable.value = true
  } finally {
    loading.value = false
  }
}

watch([slug, searchQuery, categorySlug], load, { immediate: true })

const origin = typeof window !== 'undefined' ? window.location.origin : ''

// Help centers are meant to be found by search engines (robots.txt allows
// /help/); search result pages are not worth indexing.
useHead(
  computed(() => ({
    title: helpCenterStore.center
      ? `${t('helpCenter.title')} · ${helpCenterStore.center.organization_name}`
      : t('helpCenter.title'),
    meta: [
      {
        name: 'robots',
        content: unavailable.value || searchQuery.value ? 'noindex, follow' : 'index, follow',
      },
    ],
    link: [
      {
        rel: 'canonical',
        href: `${origin}/help/${slug.value}${categorySlug.value ? `?category=${categorySlug.value}` : ''}`,
      },
    ],
  })),
)
</script>
