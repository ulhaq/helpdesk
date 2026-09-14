<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>{{ $t('knowledge.textDialog.title') }}</DialogTitle>
        <DialogDescription>{{ $t('knowledge.textDialog.description') }}</DialogDescription>
      </DialogHeader>

      <form class="space-y-4" @submit.prevent="submit">
        <div class="space-y-2">
          <Label for="knowledge-document-title">{{ $t('knowledge.textDialog.titleLabel') }}</Label>
          <Input
            id="knowledge-document-title"
            v-model="title"
            maxlength="255"
            :placeholder="$t('knowledge.textDialog.titlePlaceholder')"
            :disabled="busy"
          />
        </div>
        <div class="space-y-2">
          <Label for="knowledge-document-text">{{ $t('knowledge.textDialog.textLabel') }}</Label>
          <Textarea
            id="knowledge-document-text"
            v-model="text"
            rows="12"
            :placeholder="$t('knowledge.textDialog.textPlaceholder')"
            :disabled="busy"
          />
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="ghost"
            :disabled="busy"
            @click="$emit('update:open', false)"
          >
            {{ $t('common.cancel') }}
          </Button>
          <Button type="submit" :disabled="busy || !title.trim() || !text.trim()">
            <Loader2 v-if="busy" class="mr-2 h-4 w-4 animate-spin" />
            {{ $t('common.save') }}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from 'lucide-vue-next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/platform/components/ui/dialog'
import { Button } from '@/platform/components/ui/button'
import { Input } from '@/platform/components/ui/input'
import { Label } from '@/platform/components/ui/label'
import { Textarea } from '@/platform/components/ui/textarea'
import { useErrorHandler } from '@/platform/composables/useErrorHandler'
import { useToast } from '@/platform/composables/useToast'
import { useKnowledgeStore } from '@/helpdesk/stores/knowledge'
import type { KnowledgeDocument } from '@/helpdesk/types/knowledge'

defineProps<{ open: boolean }>()
const emit = defineEmits<{
  'update:open': [boolean]
  created: [KnowledgeDocument]
}>()

const { t } = useI18n()
const knowledgeStore = useKnowledgeStore()
const { handleError } = useErrorHandler()
const { toast } = useToast()

const busy = ref(false)
const title = ref('')
const text = ref('')

async function submit() {
  busy.value = true
  try {
    const created = await knowledgeStore.createDocument({
      title: title.value.trim(),
      text: text.value,
    })
    toast({ title: t('knowledge.created') })
    title.value = ''
    text.value = ''
    emit('update:open', false)
    emit('created', created)
  } catch (err: unknown) {
    handleError(err)
  } finally {
    busy.value = false
  }
}
</script>
