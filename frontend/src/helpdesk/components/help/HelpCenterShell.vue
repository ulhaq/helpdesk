<template>
  <div class="flex min-h-screen flex-col bg-background">
    <header :style="brandStyle">
      <div class="mx-auto max-w-4xl space-y-5 px-5 py-8">
        <RouterLink
          :to="{ name: '/help/[slug]/', params: { slug } }"
          class="inline-flex flex-col focus-visible:outline focus-visible:outline-2"
        >
          <span class="text-sm opacity-80">{{ center?.organization_name }}</span>
          <span class="text-2xl font-semibold tracking-tight">{{ $t('helpCenter.title') }}</span>
        </RouterLink>
        <form role="search" class="relative max-w-xl" @submit.prevent="submitSearch">
          <Search
            class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            v-model="query"
            type="search"
            class="h-11 bg-background pl-9 text-foreground"
            :placeholder="$t('helpCenter.searchPlaceholder')"
            :aria-label="$t('helpCenter.searchLabel')"
          />
        </form>
      </div>
    </header>

    <main class="mx-auto w-full max-w-4xl flex-1 px-5 py-8">
      <slot />
    </main>

    <footer v-if="center?.widget_enabled" class="border-t">
      <div class="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3 px-5 py-6">
        <p class="text-sm text-muted-foreground">{{ $t('helpCenter.stillNeedHelp') }}</p>
        <Button as-child :style="brandStyle">
          <RouterLink :to="{ name: '/widget/[slug]', params: { slug } }">
            {{ $t('helpCenter.contactUs') }}
          </RouterLink>
        </Button>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { Search } from 'lucide-vue-next'
import { Button } from '@/platform/components/ui/button'
import { Input } from '@/platform/components/ui/input'
import { brandColors } from '@/helpdesk/utils/brand'
import type { HelpCenter } from '@/helpdesk/types/kb'

const props = defineProps<{ slug: string; center: HelpCenter | null; initialQuery?: string }>()

const router = useRouter()
const query = ref(props.initialQuery ?? '')

watch(
  () => props.initialQuery,
  (value) => {
    query.value = value ?? ''
  },
)

const brandStyle = computed(() => brandColors(props.center?.brand_color))

function submitSearch() {
  const q = query.value.trim()
  router.push({ name: '/help/[slug]/', params: { slug: props.slug }, query: q ? { q } : {} })
}
</script>
