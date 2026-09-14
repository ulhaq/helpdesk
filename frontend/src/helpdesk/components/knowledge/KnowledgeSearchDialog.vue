<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>{{ $t('knowledge.search.title') }}</DialogTitle>
        <DialogDescription>{{ $t('knowledge.search.description') }}</DialogDescription>
      </DialogHeader>

      <form class="space-y-3" @submit.prevent="runSearch">
        <div class="space-y-2">
          <Label for="knowledge-search-query">{{ $t('knowledge.search.queryLabel') }}</Label>
          <Textarea
            id="knowledge-search-query"
            v-model="query"
            rows="3"
            maxlength="2000"
            :placeholder="$t('knowledge.search.queryPlaceholder')"
            :disabled="searching"
            @keydown.enter.exact.prevent="runSearch"
          />
        </div>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <label class="flex cursor-pointer items-center gap-2 text-sm">
            <Checkbox
              :model-value="includeInternal"
              @update:model-value="includeInternal = $event === true"
            />
            {{ $t('knowledge.search.includeInternal') }}
          </label>
          <Button type="submit" size="sm" :disabled="searching || !query.trim()">
            <Loader2 v-if="searching" class="mr-2 h-4 w-4 animate-spin" />
            <Search v-else class="mr-2 h-4 w-4" />
            {{ $t('knowledge.search.submit') }}
          </Button>
        </div>
      </form>

      <div v-if="result" class="space-y-3" aria-live="polite">
        <div class="space-y-1 text-xs text-muted-foreground">
          <p>
            {{
              result.terms.length
                ? $t('knowledge.search.terms', { terms: result.terms.join(', ') })
                : $t('knowledge.search.noTerms')
            }}
          </p>
          <p v-if="result.sends_everything">{{ $t('knowledge.search.sendsEverything') }}</p>
          <p v-if="result.semantic === 'off'">{{ $t('knowledge.search.semanticOff') }}</p>
          <p v-else-if="result.semantic === 'unavailable'" class="text-warning">
            {{ $t('knowledge.search.semanticUnavailable') }}
          </p>
          <p v-if="result.pending_embeddings">
            {{
              $t(
                'knowledge.search.pending',
                { n: result.pending_embeddings },
                result.pending_embeddings,
              )
            }}
          </p>
        </div>

        <p v-if="!result.results.length" class="text-sm text-muted-foreground">
          {{ $t('knowledge.search.empty') }}
        </p>
        <ol v-else class="divide-y rounded-lg border">
          <li v-for="(item, index) in result.results" :key="item.chunk_id" class="space-y-1.5 p-3">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-xs tabular-nums text-muted-foreground">{{ index + 1 }}.</span>
              <span class="text-sm font-medium">{{ item.title }}</span>
              <Badge v-if="item.source_type === 'document'" variant="warning" class="text-xs">
                {{ $t('knowledge.search.internal') }}
              </Badge>
              <Badge :variant="item.selected ? 'success' : 'outline'" class="ml-auto text-xs">
                {{
                  item.selected
                    ? $t('knowledge.search.selected')
                    : $t('knowledge.search.notSelected')
                }}
              </Badge>
            </div>
            <p v-if="item.heading !== item.title" class="text-xs text-muted-foreground">
              {{ item.heading }}
            </p>
            <p class="line-clamp-3 whitespace-pre-wrap text-sm text-muted-foreground">
              {{ item.excerpt }}
            </p>
            <p class="text-xs tabular-nums text-muted-foreground">
              {{
                item.keyword_rank
                  ? $t('knowledge.search.keywordRank', { rank: item.keyword_rank })
                  : $t('knowledge.search.noKeywordMatch')
              }}
              <template v-if="result.semantic === 'ok'">
                ·
                {{
                  item.semantic_rank && item.distance !== null
                    ? $t('knowledge.search.semanticRank', {
                        rank: item.semantic_rank,
                        distance: item.distance.toFixed(3),
                      })
                    : $t('knowledge.search.noSemanticMatch')
                }}
              </template>
            </p>
          </li>
        </ol>
      </div>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Loader2, Search } from 'lucide-vue-next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/platform/components/ui/dialog'
import { Badge } from '@/platform/components/ui/badge'
import { Button } from '@/platform/components/ui/button'
import { Checkbox } from '@/platform/components/ui/checkbox'
import { Label } from '@/platform/components/ui/label'
import { Textarea } from '@/platform/components/ui/textarea'
import { useErrorHandler } from '@/platform/composables/useErrorHandler'
import { useKnowledgeStore } from '@/helpdesk/stores/knowledge'
import type { KnowledgeSearchOut } from '@/helpdesk/types/knowledge'

defineProps<{ open: boolean }>()
defineEmits<{ 'update:open': [boolean] }>()

const knowledgeStore = useKnowledgeStore()
const { handleError } = useErrorHandler()

const query = ref('')
const includeInternal = ref(true)
const searching = ref(false)
const result = ref<KnowledgeSearchOut | null>(null)

async function runSearch() {
  const question = query.value.trim()
  if (!question || searching.value) return
  searching.value = true
  try {
    result.value = await knowledgeStore.search({
      query: question,
      include_internal: includeInternal.value,
    })
  } catch (err: unknown) {
    handleError(err)
  } finally {
    searching.value = false
  }
}
</script>
