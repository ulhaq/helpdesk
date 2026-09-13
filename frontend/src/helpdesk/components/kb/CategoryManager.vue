<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>{{ $t('kb.categories.title') }}</DialogTitle>
        <DialogDescription>{{ $t('kb.categories.description') }}</DialogDescription>
      </DialogHeader>

      <ul
        v-if="kbStore.categories.length"
        class="max-h-80 divide-y overflow-y-auto rounded-md border"
      >
        <li
          v-for="category in kbStore.categories"
          :key="category.id"
          class="flex items-center gap-2 px-3 py-2"
        >
          <form
            v-if="editingId === category.id"
            class="flex flex-1 items-center gap-2"
            @submit.prevent="saveEdit(category)"
          >
            <Input
              v-model="editName"
              class="h-8"
              :aria-label="$t('common.name')"
              :disabled="busy"
              @keydown.esc="editingId = null"
            />
            <Button type="submit" size="sm" class="h-8" :disabled="busy || !editName.trim()">
              {{ $t('common.save') }}
            </Button>
            <Button type="button" size="sm" variant="ghost" class="h-8" @click="editingId = null">
              {{ $t('common.cancel') }}
            </Button>
          </form>
          <template v-else>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium">{{ category.name }}</p>
              <p class="truncate text-xs text-muted-foreground">/{{ category.slug }}</p>
            </div>
            <Button
              size="sm"
              variant="ghost"
              class="h-8 w-8 p-0"
              :aria-label="$t('common.edit')"
              :disabled="busy"
              @click="startEdit(category)"
            >
              <Pencil class="h-4 w-4" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              class="h-8 w-8 p-0 text-destructive hover:text-destructive"
              :aria-label="$t('common.delete')"
              :disabled="busy"
              @click="remove(category)"
            >
              <Trash2 class="h-4 w-4" />
            </Button>
          </template>
        </li>
      </ul>
      <p v-else class="text-sm text-muted-foreground">{{ $t('kb.categories.empty') }}</p>

      <form class="flex gap-2" @submit.prevent="create">
        <Input
          v-model="newName"
          :placeholder="$t('kb.categories.newPlaceholder')"
          :aria-label="$t('kb.categories.newPlaceholder')"
          :disabled="busy"
        />
        <Button type="submit" :disabled="busy || !newName.trim()">
          <Plus class="mr-1 h-4 w-4" />
          {{ $t('common.create') }}
        </Button>
      </form>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Pencil, Plus, Trash2 } from 'lucide-vue-next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/platform/components/ui/dialog'
import { Button } from '@/platform/components/ui/button'
import { Input } from '@/platform/components/ui/input'
import { useConfirm } from '@/platform/composables/useConfirm'
import { useErrorHandler } from '@/platform/composables/useErrorHandler'
import { useToast } from '@/platform/composables/useToast'
import { useKbStore } from '@/helpdesk/stores/kb'
import type { KbCategory } from '@/helpdesk/types/kb'

defineProps<{ open: boolean }>()
defineEmits<{ 'update:open': [boolean] }>()

const { t } = useI18n()
const kbStore = useKbStore()
const { confirm } = useConfirm()
const { handleError } = useErrorHandler()
const { toast } = useToast()

const busy = ref(false)
const newName = ref('')
const editingId = ref<number | null>(null)
const editName = ref('')

async function run(action: () => Promise<void>) {
  busy.value = true
  try {
    await action()
  } catch (err: unknown) {
    handleError(err)
  } finally {
    busy.value = false
  }
}

function create() {
  return run(async () => {
    await kbStore.createCategory({
      name: newName.value.trim(),
      position: kbStore.categories.length,
    })
    newName.value = ''
    toast({ title: t('kb.categories.created') })
  })
}

function startEdit(category: KbCategory) {
  editingId.value = category.id
  editName.value = category.name
}

function saveEdit(category: KbCategory) {
  return run(async () => {
    await kbStore.patchCategory(category.id, { name: editName.value.trim() })
    editingId.value = null
    toast({ title: t('kb.categories.saved') })
  })
}

async function remove(category: KbCategory) {
  const ok = await confirm(
    t('kb.categories.deleteTitle'),
    t('kb.categories.deleteDescription', { name: category.name }),
    t('common.delete'),
  )
  if (!ok) return
  await run(async () => {
    await kbStore.removeCategory(category.id)
    toast({ title: t('kb.categories.deleted') })
  })
}
</script>
