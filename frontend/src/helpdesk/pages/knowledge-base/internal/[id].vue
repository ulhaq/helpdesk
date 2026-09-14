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
      to="/knowledge-base/internal"
      class="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft class="w-4 h-4" />
      {{ $t('knowledge.back') }}
    </RouterLink>

    <Skeleton v-if="loading" class="h-96 w-full" />

    <EmptyState
      v-else-if="!knowledgeDocument"
      :title="$t('knowledge.editor.notFoundTitle')"
      :description="$t('knowledge.editor.notFoundDescription')"
      :icon="Lock"
    />

    <template v-else>
      <PageHeader :title="$t('knowledge.editor.title')">
        <template #actions>
          <Button variant="outline" size="sm" @click="handleDelete">
            <Trash2 class="w-4 h-4 mr-2" />
            {{ $t('common.delete') }}
          </Button>
        </template>
      </PageHeader>

      <form class="max-w-3xl space-y-4" @submit.prevent="save">
        <div class="space-y-2">
          <Label for="knowledge-document-title">{{ $t('knowledge.editor.titleLabel') }}</Label>
          <Input id="knowledge-document-title" v-model="title" maxlength="255" :disabled="saving" />
        </div>
        <div class="space-y-2">
          <Label for="knowledge-document-text">{{ $t('knowledge.editor.textLabel') }}</Label>
          <Textarea
            id="knowledge-document-text"
            v-model="text"
            rows="20"
            class="font-mono text-sm"
            :disabled="saving"
          />
          <p class="text-xs text-muted-foreground">
            {{
              knowledgeDocument.filename
                ? $t('knowledge.editor.textHintFile', { filename: knowledgeDocument.filename })
                : $t('knowledge.editor.textHintText')
            }}
          </p>
        </div>
        <div class="flex justify-end">
          <Button type="submit" :disabled="saving || !dirty || !title.trim() || !text.trim()">
            <Loader2 v-if="saving" class="w-4 h-4 mr-2 animate-spin" />
            {{ $t('common.save') }}
          </Button>
        </div>
      </form>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Loader2, Lock, Trash2 } from 'lucide-vue-next'
import { Button } from '@/platform/components/ui/button'
import { Input } from '@/platform/components/ui/input'
import { Label } from '@/platform/components/ui/label'
import { Skeleton } from '@/platform/components/ui/skeleton'
import { Textarea } from '@/platform/components/ui/textarea'
import EmptyState from '@/platform/components/common/EmptyState.vue'
import PageHeader from '@/platform/components/common/PageHeader.vue'
import { useConfirm } from '@/platform/composables/useConfirm'
import { useErrorHandler } from '@/platform/composables/useErrorHandler'
import { useToast } from '@/platform/composables/useToast'
import { useKnowledgeStore } from '@/helpdesk/stores/knowledge'
import type { KnowledgeDocument, KnowledgeDocumentPatch } from '@/helpdesk/types/knowledge'

const { t } = useI18n()
const route = useRoute('/knowledge-base/internal/[id]')
const router = useRouter()
const knowledgeStore = useKnowledgeStore()
const { confirm } = useConfirm()
const { handleError } = useErrorHandler()
const { toast } = useToast()

const knowledgeDocument = ref<KnowledgeDocument | null>(null)
const loading = ref(true)
const saving = ref(false)
const title = ref('')
const text = ref('')

const dirty = computed(
  () =>
    knowledgeDocument.value !== null &&
    (title.value !== knowledgeDocument.value.title || text.value !== knowledgeDocument.value.text),
)

function show(loaded: KnowledgeDocument | null) {
  knowledgeDocument.value = loaded
  title.value = loaded?.title ?? ''
  text.value = loaded?.text ?? ''
}

watch(
  () => route.params.id,
  async (id) => {
    loading.value = true
    try {
      show(await knowledgeStore.getDocument(Number(id)))
    } catch {
      show(null)
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

async function save() {
  const current = knowledgeDocument.value
  if (!current) return
  const changes: KnowledgeDocumentPatch = {}
  if (title.value !== current.title) changes.title = title.value.trim()
  if (text.value !== current.text) changes.text = text.value
  saving.value = true
  try {
    show(await knowledgeStore.patchDocument(current.id, changes))
    toast({ title: t('knowledge.editor.saved') })
  } catch (err: unknown) {
    handleError(err)
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  const current = knowledgeDocument.value
  if (!current) return
  const ok = await confirm(
    t('knowledge.deleteTitle'),
    t('knowledge.deleteDescription', { title: current.title }),
    t('common.delete'),
  )
  if (!ok) return
  try {
    await knowledgeStore.removeDocument(current.id)
    toast({ title: t('knowledge.deleted') })
    router.push('/knowledge-base/internal')
  } catch (err: unknown) {
    handleError(err, t('knowledge.deleteFailed'))
  }
}
</script>
