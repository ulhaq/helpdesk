<template>
  <form class="grid gap-6 lg:grid-cols-[1fr_18rem]" @submit.prevent="save()">
    <div class="min-w-0 space-y-4">
      <div class="space-y-2">
        <Label for="article-title">{{ $t('kb.editor.titleLabel') }}</Label>
        <Input
          id="article-title"
          v-model="form.title"
          class="h-11 text-lg"
          :placeholder="$t('kb.editor.titlePlaceholder')"
          :disabled="saving"
        />
      </div>

      <Tabs v-model="tab" class="space-y-2">
        <TabsList>
          <TabsTrigger value="write">{{ $t('kb.editor.write') }}</TabsTrigger>
          <TabsTrigger value="preview">{{ $t('kb.editor.preview') }}</TabsTrigger>
        </TabsList>
        <TabsContent value="write" class="space-y-2">
          <Textarea
            v-model="form.body"
            rows="20"
            class="font-mono text-sm"
            :aria-label="$t('kb.editor.bodyLabel')"
            :placeholder="$t('kb.editor.bodyPlaceholder')"
            :disabled="saving"
          />
          <p class="text-xs text-muted-foreground">{{ $t('kb.editor.markdownHint') }}</p>
        </TabsContent>
        <TabsContent value="preview" class="min-h-64 rounded-md border bg-card p-5">
          <div v-if="previewLoading" class="space-y-2">
            <Skeleton class="h-5 w-2/3" />
            <Skeleton class="h-20 w-full" />
          </div>
          <MarkdownContent v-else-if="previewHtml" :html="previewHtml" />
          <p v-else class="text-sm text-muted-foreground">{{ $t('kb.editor.previewEmpty') }}</p>
        </TabsContent>
      </Tabs>
    </div>

    <aside class="space-y-4">
      <div class="space-y-4 rounded-lg border bg-card p-4">
        <div v-if="article" class="flex items-center justify-between gap-2">
          <ArticleStatusBadge :status="article.status" />
          <span class="text-xs text-muted-foreground">{{
            formatDateTime(article.updated_at)
          }}</span>
        </div>

        <div class="space-y-2">
          <Label for="article-slug">{{ $t('kb.editor.slug') }}</Label>
          <Input
            id="article-slug"
            v-model="form.slug"
            class="font-mono text-sm"
            :placeholder="$t('kb.editor.slugPlaceholder')"
            :disabled="saving"
          />
          <p class="text-xs text-muted-foreground">{{ $t('kb.editor.slugHint') }}</p>
        </div>

        <div class="space-y-2">
          <Label>{{ $t('kb.editor.category') }}</Label>
          <Select v-model="form.categoryId" :disabled="saving">
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem :value="NO_CATEGORY">{{ $t('kb.editor.noCategory') }}</SelectItem>
              <SelectItem
                v-for="category in kbStore.categories"
                :key="category.id"
                :value="String(category.id)"
              >
                {{ category.name }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <p v-if="errorMessage" class="text-sm text-destructive" role="alert">{{ errorMessage }}</p>

        <div class="flex flex-col gap-2">
          <template v-if="isPublished">
            <Button type="submit" :disabled="saving || !canSave">
              <Loader2 v-if="saving" class="mr-2 h-4 w-4 animate-spin" />
              {{ $t('kb.editor.saveChanges') }}
            </Button>
            <Button type="button" variant="outline" :disabled="saving" @click="save('draft')">
              {{ $t('kb.editor.unpublish') }}
            </Button>
          </template>
          <template v-else>
            <Button
              type="button"
              :disabled="saving || !form.title.trim()"
              @click="save('published')"
            >
              <Loader2 v-if="saving" class="mr-2 h-4 w-4 animate-spin" />
              {{ $t('kb.editor.publish') }}
            </Button>
            <Button type="submit" variant="outline" :disabled="saving || !canSave">
              {{ $t('kb.editor.saveDraft') }}
            </Button>
          </template>
        </div>
      </div>
    </aside>
  </form>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from 'lucide-vue-next'
import { Button } from '@/platform/components/ui/button'
import { Input } from '@/platform/components/ui/input'
import { Label } from '@/platform/components/ui/label'
import { Skeleton } from '@/platform/components/ui/skeleton'
import { Textarea } from '@/platform/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/platform/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/platform/components/ui/select'
import { useErrorHandler } from '@/platform/composables/useErrorHandler'
import { useFormatDate } from '@/platform/composables/useFormatDate'
import { useToast } from '@/platform/composables/useToast'
import ArticleStatusBadge from '@/helpdesk/components/kb/ArticleStatusBadge.vue'
import MarkdownContent from '@/helpdesk/components/kb/MarkdownContent.vue'
import { useKbStore } from '@/helpdesk/stores/kb'
import type { ArticleStatus, KbArticle } from '@/helpdesk/types/kb'

const NO_CATEGORY = '__none__'

const props = defineProps<{ article?: KbArticle | null }>()
const emit = defineEmits<{ saved: [article: KbArticle] }>()

const { t } = useI18n()
const kbStore = useKbStore()
const { toast } = useToast()
const { resolveError, resolveFieldErrors } = useErrorHandler()
const { formatDateTime } = useFormatDate()

const form = reactive({ title: '', slug: '', body: '', categoryId: NO_CATEGORY })
const saving = ref(false)
const errorMessage = ref('')
const tab = ref('write')
const previewHtml = ref('')
const previewLoading = ref(false)

const isPublished = computed(() => props.article?.status === 'published')

const isDirty = computed(() => {
  const article = props.article
  if (!article) return true
  return (
    form.title !== article.title ||
    form.slug !== article.slug ||
    form.body !== article.body ||
    form.categoryId !== (article.category_id === null ? NO_CATEGORY : String(article.category_id))
  )
})
const canSave = computed(() => form.title.trim() !== '' && isDirty.value)

watch(
  () => props.article,
  (article) => {
    form.title = article?.title ?? ''
    form.slug = article?.slug ?? ''
    form.body = article?.body ?? ''
    form.categoryId = article?.category_id == null ? NO_CATEGORY : String(article.category_id)
    errorMessage.value = ''
  },
  { immediate: true },
)

onMounted(() => {
  kbStore.loadCategories().catch(() => undefined)
})

watch(tab, async (value) => {
  if (value !== 'preview') return
  if (!form.body.trim()) {
    previewHtml.value = ''
    return
  }
  previewLoading.value = true
  try {
    previewHtml.value = await kbStore.preview(form.body)
  } catch (err: unknown) {
    errorMessage.value = resolveError(err)
  } finally {
    previewLoading.value = false
  }
})

async function save(status?: ArticleStatus) {
  if (!form.title.trim()) return
  saving.value = true
  errorMessage.value = ''
  const payload = {
    title: form.title.trim(),
    body: form.body,
    category_id: form.categoryId === NO_CATEGORY ? null : Number(form.categoryId),
    ...(form.slug.trim() ? { slug: form.slug.trim() } : {}),
    ...(status ? { status } : {}),
  }
  try {
    const saved = props.article
      ? await kbStore.patchArticle(props.article.id, payload)
      : await kbStore.createArticle(payload)
    const message =
      status === 'published'
        ? 'kb.editor.published'
        : status === 'draft' && isPublished.value
          ? 'kb.editor.unpublished'
          : 'kb.editor.saved'
    toast({ title: t(message) })
    emit('saved', saved)
  } catch (err: unknown) {
    const fieldErrors = resolveFieldErrors(err)
    errorMessage.value =
      fieldErrors['body__slug'] ?? fieldErrors['body__title'] ?? resolveError(err)
  } finally {
    saving.value = false
  }
}
</script>
