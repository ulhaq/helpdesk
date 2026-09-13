<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>{{ $t('tickets.form.title') }}</DialogTitle>
        <DialogDescription>{{ $t('tickets.form.description') }}</DialogDescription>
      </DialogHeader>

      <form class="space-y-4" @submit.prevent="onSubmit">
        <div class="grid gap-4 sm:grid-cols-2">
          <div class="space-y-2">
            <Label for="ticket-contact-name">{{ $t('tickets.form.customerName') }}</Label>
            <Input
              id="ticket-contact-name"
              v-model="form.contactName"
              autocomplete="off"
              :disabled="isLoading"
            />
            <p v-if="errors.contactName" class="text-xs text-destructive">
              {{ errors.contactName }}
            </p>
          </div>
          <div class="space-y-2">
            <Label for="ticket-contact-email">{{ $t('tickets.form.customerEmail') }}</Label>
            <Input
              id="ticket-contact-email"
              v-model="form.contactEmail"
              type="email"
              autocomplete="off"
              :disabled="isLoading"
            />
            <p v-if="errors.contactEmail" class="text-xs text-destructive">
              {{ errors.contactEmail }}
            </p>
          </div>
        </div>
        <p class="text-xs text-muted-foreground">{{ $t('tickets.form.customerHint') }}</p>

        <div class="grid gap-4 sm:grid-cols-[1fr_10rem]">
          <div class="space-y-2">
            <Label for="ticket-subject">{{ $t('tickets.form.subject') }}</Label>
            <Input
              id="ticket-subject"
              v-model="form.subject"
              :placeholder="$t('tickets.form.subjectPlaceholder')"
              :disabled="isLoading"
            />
            <p v-if="errors.subject" class="text-xs text-destructive">{{ errors.subject }}</p>
          </div>
          <div class="space-y-2">
            <Label>{{ $t('tickets.columns.priority') }}</Label>
            <Select v-model="priority" :disabled="isLoading">
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="p in TICKET_PRIORITIES" :key="p" :value="p">
                  {{ $t(`tickets.priority.${p}`) }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div class="space-y-2">
          <Label for="ticket-body">{{ $t('tickets.form.body') }}</Label>
          <Textarea
            id="ticket-body"
            v-model="form.body"
            :placeholder="$t('tickets.form.bodyPlaceholder')"
            :disabled="isLoading"
            rows="5"
          />
          <p v-if="errors.body" class="text-xs text-destructive">{{ errors.body }}</p>
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
          <Button type="submit" :disabled="isLoading">
            <Loader2 v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
            {{ $t('common.create') }}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
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
import { useTicketsStore } from '@/helpdesk/stores/tickets'
import { TICKET_PRIORITIES } from '@/helpdesk/constants'
import type { TicketDetailOut, TicketPriority } from '@/helpdesk/types/ticket'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [boolean]; created: [ticket: TicketDetailOut] }>()

const { t } = useI18n()
const { toast } = useToast()
const ticketsStore = useTicketsStore()
const { resolveError } = useErrorHandler()
const rules = useRules()
const { form, errors, validate, clearErrors } = useValidation({
  contactName: rules.required,
  contactEmail: rules.email,
  subject: rules.required,
  body: rules.required,
})
const priority = ref<TicketPriority>('normal')
const isLoading = ref(false)
const errorMessage = ref('')

watch(
  () => props.open,
  (open) => {
    if (!open) return
    form.contactName = ''
    form.contactEmail = ''
    form.subject = ''
    form.body = ''
    priority.value = 'normal'
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
    const ticket = await ticketsStore.create({
      subject: form.subject,
      body: form.body,
      priority: priority.value,
      contact: { name: form.contactName, email: form.contactEmail },
    })
    toast({ title: t('tickets.form.created', { number: ticket.number }) })
    emit('update:open', false)
    emit('created', ticket)
  } catch (err: unknown) {
    errorMessage.value = resolveError(err)
  } finally {
    isLoading.value = false
  }
}
</script>
