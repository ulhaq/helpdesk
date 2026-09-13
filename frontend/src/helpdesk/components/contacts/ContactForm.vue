<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>{{
          isEdit ? $t('contacts.form.editTitle') : $t('contacts.form.createTitle')
        }}</DialogTitle>
        <DialogDescription>
          {{ isEdit ? $t('contacts.form.editDescription') : $t('contacts.form.createDescription') }}
        </DialogDescription>
      </DialogHeader>

      <form class="space-y-4" @submit.prevent="onSubmit">
        <div class="space-y-2">
          <Label for="contact-name">{{ $t('common.name') }}</Label>
          <Input id="contact-name" v-model="form.name" :disabled="isLoading" />
          <p v-if="errors.name" class="text-xs text-destructive">{{ errors.name }}</p>
        </div>
        <div class="space-y-2">
          <Label for="contact-email">{{ $t('common.email') }}</Label>
          <Input id="contact-email" v-model="form.email" type="email" :disabled="isLoading" />
          <p v-if="errors.email" class="text-xs text-destructive">{{ errors.email }}</p>
        </div>
        <div class="space-y-2">
          <Label>{{ $t('contacts.form.language') }}</Label>
          <Select v-model="locale" :disabled="isLoading">
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem :value="NO_LOCALE">{{ $t('contacts.form.languageDefault') }}</SelectItem>
              <SelectItem v-for="code in LOCALE_ORDER" :key="code" :value="code">
                {{ LOCALE_LABELS[code] }}
              </SelectItem>
            </SelectContent>
          </Select>
          <p class="text-xs text-muted-foreground">{{ $t('contacts.form.languageHint') }}</p>
        </div>
        <div class="space-y-2">
          <Label for="contact-notes"
            >{{ $t('contacts.form.notes') }}
            <span class="text-muted-foreground">({{ $t('common.optional') }})</span></Label
          >
          <Textarea
            id="contact-notes"
            v-model="form.notes"
            :placeholder="$t('contacts.form.notesPlaceholder')"
            :disabled="isLoading"
            rows="3"
          />
        </div>

        <p v-if="errorMessage" class="text-sm text-destructive">{{ errorMessage }}</p>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            :disabled="isLoading"
            @click="$emit('update:open', false)"
            >{{ $t('common.cancel') }}</Button
          >
          <Button type="submit" :disabled="isLoading || (isEdit && !isDirty)">
            <Loader2 v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
            {{ isEdit ? $t('common.saveChanges') : $t('common.create') }}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { reactive, ref, computed, watch } from 'vue'
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
import { Textarea } from '@/platform/components/ui/textarea'
import { Label } from '@/platform/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/platform/components/ui/select'
import { useToast } from '@/platform/composables/useToast'
import { useErrorHandler } from '@/platform/composables/useErrorHandler'
import { useValidation } from '@/platform/composables/useValidation'
import { useRules } from '@/platform/composables/useRules'
import { LOCALE_LABELS, LOCALE_ORDER, type SupportedLocale } from '@/plugins/i18n'
import { useContactsStore } from '@/helpdesk/stores/contacts'
import type { ContactOut } from '@/helpdesk/types/contact'

const NO_LOCALE = '__none__'

const props = defineProps<{ open: boolean; contact?: ContactOut | null }>()
const emit = defineEmits<{ 'update:open': [boolean]; saved: [contact: ContactOut] }>()

const { t } = useI18n()
const { toast } = useToast()
const contactsStore = useContactsStore()
const { resolveError, resolveFieldErrors } = useErrorHandler()
const rules = useRules()
const isEdit = computed(() => !!props.contact)
const { form, errors, validate, clearErrors } = useValidation({
  name: rules.required,
  email: rules.email,
  notes: [],
})
const locale = ref<string>(NO_LOCALE)
const isLoading = ref(false)
const errorMessage = ref('')
const baseline = reactive({ name: '', email: '', notes: '', locale: NO_LOCALE })

const isDirty = computed(
  () =>
    form.name !== baseline.name ||
    form.email !== baseline.email ||
    form.notes !== baseline.notes ||
    locale.value !== baseline.locale,
)

watch(
  [() => props.open, () => props.contact],
  ([open]) => {
    if (!open) return
    form.name = props.contact?.name ?? ''
    form.email = props.contact?.email ?? ''
    form.notes = props.contact?.notes ?? ''
    locale.value = props.contact?.locale ?? NO_LOCALE
    Object.assign(baseline, {
      name: form.name,
      email: form.email,
      notes: form.notes,
      locale: locale.value,
    })
    clearErrors()
    errorMessage.value = ''
  },
  { immediate: true },
)

async function onSubmit() {
  if (!validate()) return
  isLoading.value = true
  errorMessage.value = ''
  try {
    const payload = {
      name: form.name,
      email: form.email,
      notes: form.notes || null,
      locale: locale.value === NO_LOCALE ? null : (locale.value as SupportedLocale),
    }
    const saved =
      isEdit.value && props.contact
        ? await contactsStore.patch(props.contact.id, payload)
        : await contactsStore.create(payload)
    toast({ title: isEdit.value ? t('contacts.form.saved') : t('contacts.form.created') })
    emit('update:open', false)
    emit('saved', saved)
  } catch (err: unknown) {
    const fieldErrors = resolveFieldErrors(err)
    errorMessage.value = fieldErrors['body__email'] ?? resolveError(err)
  } finally {
    isLoading.value = false
  }
}
</script>
