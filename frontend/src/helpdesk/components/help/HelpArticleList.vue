<template>
  <p v-if="!articles.length" class="text-sm text-muted-foreground">{{ emptyText }}</p>
  <ul v-else class="divide-y rounded-lg border">
    <li v-for="article in articles" :key="article.slug">
      <RouterLink
        :to="{ name: '/help/[slug]/articles/[article]', params: { slug, article: article.slug } }"
        class="block px-4 py-3 transition-colors hover:bg-muted/50"
      >
        <p class="font-medium">{{ article.title }}</p>
        <p v-if="article.excerpt" class="mt-1 line-clamp-2 text-sm text-muted-foreground">
          {{ article.excerpt }}
        </p>
        <p v-if="article.category" class="mt-1 text-xs text-muted-foreground">
          {{ article.category.name }}
        </p>
      </RouterLink>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import type { HelpArticleSummary } from '@/helpdesk/types/kb'

defineProps<{ slug: string; articles: HelpArticleSummary[]; emptyText: string }>()
</script>
