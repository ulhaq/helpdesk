<route lang="yaml">
meta:
  layout: dashboard
  requiresAuth: true
  permission: read:ticket
  breadcrumb: nav.tickets
</route>

<template>
  <div class="animate-fade-in">
    <RouterLink
      to="/tickets"
      class="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft class="w-4 h-4" />
      {{ $t('tickets.detail.back') }}
    </RouterLink>

    <div v-if="loading && !ticket" class="space-y-4">
      <Skeleton class="h-8 w-2/3" />
      <Skeleton class="h-40 w-full" />
    </div>

    <EmptyState
      v-else-if="notFound || !ticket"
      :title="$t('tickets.detail.notFoundTitle')"
      :description="$t('tickets.detail.notFoundDescription')"
      :icon="Inbox"
    />

    <template v-else>
      <PageHeader :title="`#${ticket.number} ${ticket.subject}`">
        <template #title-suffix>
          <TicketStatusBadge :status="ticket.status" />
        </template>
        <template #actions>
          <PermissionGuard permission="delete:ticket">
            <Button variant="outline" size="sm" @click="handleDelete">
              <Trash2 class="w-4 h-4 mr-2" />
              {{ $t('common.delete') }}
            </Button>
          </PermissionGuard>
        </template>
      </PageHeader>

      <div class="grid gap-6 lg:grid-cols-3">
        <div class="space-y-4 lg:col-span-2">
          <ol class="space-y-3">
            <li
              v-for="message in ticket.messages"
              :key="message.id"
              :class="
                cn(
                  'rounded-lg border p-4',
                  message.is_internal
                    ? 'border-warning/30 bg-warning/5'
                    : message.author_type === 'contact'
                      ? 'bg-muted/40'
                      : 'bg-card',
                )
              "
            >
              <div class="mb-2 flex flex-wrap items-center gap-2 text-sm">
                <span class="font-medium">
                  {{ message.author_name ?? $t('tickets.detail.unknownAuthor') }}
                </span>
                <Badge v-if="message.is_internal" variant="warning" class="text-xs">
                  <Lock class="w-3 h-3 mr-1" />
                  {{ $t('tickets.detail.internalBadge') }}
                </Badge>
                <Badge
                  v-else-if="message.author_type === 'contact'"
                  variant="secondary"
                  class="text-xs"
                >
                  {{ $t('tickets.detail.customerBadge') }}
                </Badge>
                <span
                  class="ml-auto text-xs text-muted-foreground"
                  :title="formatDateTime(message.created_at)"
                >
                  {{ formatRelativeTime(message.created_at) }}
                </span>
              </div>
              <p class="whitespace-pre-wrap break-words text-sm">{{ message.body }}</p>
            </li>
          </ol>

          <PermissionGuard permission="reply:ticket">
            <form class="space-y-3 rounded-lg border bg-card p-4" @submit.prevent="send">
              <div class="flex gap-1" role="group">
                <Button
                  type="button"
                  size="sm"
                  :variant="mode === 'reply' ? 'secondary' : 'ghost'"
                  :aria-pressed="mode === 'reply'"
                  :disabled="isClosed"
                  @click="mode = 'reply'"
                >
                  <Send class="w-4 h-4 mr-2" />
                  {{ $t('tickets.detail.reply') }}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  :variant="mode === 'note' ? 'secondary' : 'ghost'"
                  :aria-pressed="mode === 'note'"
                  @click="mode = 'note'"
                >
                  <Lock class="w-4 h-4 mr-2" />
                  {{ $t('tickets.detail.internalNote') }}
                </Button>
                <Button
                  v-if="ticketsStore.assistantEnabled && mode === 'reply' && !isClosed"
                  type="button"
                  size="sm"
                  variant="ghost"
                  class="ml-auto"
                  :disabled="drafting || sending"
                  @click="draftReply"
                >
                  <Loader2 v-if="drafting" class="w-4 h-4 mr-2 animate-spin" />
                  <Sparkles v-else class="w-4 h-4 mr-2" />
                  {{ $t('tickets.detail.draftWithAi') }}
                </Button>
              </div>
              <Textarea
                v-model="body"
                rows="5"
                :aria-label="
                  mode === 'note' ? $t('tickets.detail.internalNote') : $t('tickets.detail.reply')
                "
                :placeholder="
                  mode === 'note'
                    ? $t('tickets.detail.notePlaceholder')
                    : $t('tickets.detail.replyPlaceholder')
                "
                :disabled="sending || drafting"
              />
              <p v-if="draftSources.length" class="text-xs text-muted-foreground">
                {{
                  $t('tickets.detail.draftSources', {
                    titles: draftSources.map((source) => source.title).join(', '),
                  })
                }}
              </p>
              <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="text-xs text-muted-foreground">{{ composerHint }}</p>
                <Button type="submit" size="sm" :disabled="sending || !body.trim()">
                  <Loader2 v-if="sending" class="w-4 h-4 mr-2 animate-spin" />
                  {{
                    mode === 'note' ? $t('tickets.detail.addNote') : $t('tickets.detail.sendReply')
                  }}
                </Button>
              </div>
            </form>
          </PermissionGuard>
        </div>

        <aside class="space-y-4">
          <div class="space-y-4 rounded-lg border bg-card p-4">
            <div class="space-y-1">
              <p class="text-xs font-medium text-muted-foreground">
                {{ $t('tickets.detail.customer') }}
              </p>
              <p class="text-sm font-medium">{{ ticket.contact.name }}</p>
              <a
                :href="`mailto:${ticket.contact.email}`"
                class="break-all text-sm text-muted-foreground hover:text-foreground"
                >{{ ticket.contact.email }}</a
              >
            </div>

            <Separator />

            <div class="space-y-2">
              <Label>{{ $t('tickets.columns.status') }}</Label>
              <Select
                :model-value="ticket.status"
                :disabled="!canUpdate || updating"
                @update:model-value="(value) => update({ status: value as TicketStatus })"
              >
                <SelectTrigger class="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="s in TICKET_STATUSES" :key="s" :value="s">
                    {{ $t(`tickets.status.${s}`) }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div class="space-y-2">
              <Label>{{ $t('tickets.columns.priority') }}</Label>
              <Select
                :model-value="ticket.priority"
                :disabled="!canUpdate || updating"
                @update:model-value="(value) => update({ priority: value as TicketPriority })"
              >
                <SelectTrigger class="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="p in TICKET_PRIORITIES" :key="p" :value="p">
                    {{ $t(`tickets.priority.${p}`) }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div class="space-y-2">
              <Label>{{ $t('tickets.columns.assignee') }}</Label>
              <Select
                :model-value="ticket.assignee ? String(ticket.assignee.id) : UNASSIGNED"
                :disabled="!canAssign || updating"
                @update:model-value="(value) => assign(value === UNASSIGNED ? null : Number(value))"
              >
                <SelectTrigger class="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem :value="UNASSIGNED">{{ $t('tickets.unassigned') }}</SelectItem>
                  <SelectItem
                    v-for="option in assigneeOptions"
                    :key="option.id"
                    :value="String(option.id)"
                  >
                    {{ option.name }}
                  </SelectItem>
                </SelectContent>
              </Select>
              <Button
                v-if="canAssign && currentUser && ticket.assignee?.id !== currentUser.id"
                variant="link"
                size="sm"
                class="h-auto p-0"
                :disabled="updating"
                @click="assign(currentUser.id)"
              >
                <UserCheck class="w-4 h-4 mr-1" />
                {{ $t('tickets.detail.assignToMe') }}
              </Button>
            </div>

            <Separator />

            <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
              <dt class="text-muted-foreground">{{ $t('tickets.detail.created') }}</dt>
              <dd class="text-right">{{ formatDateTime(ticket.created_at) }}</dd>
              <dt class="text-muted-foreground">{{ $t('tickets.detail.firstResponse') }}</dt>
              <dd class="text-right">
                {{
                  ticket.first_response_at
                    ? formatDateTime(ticket.first_response_at)
                    : $t('tickets.detail.noResponse')
                }}
              </dd>
              <template v-if="ticket.resolved_at">
                <dt class="text-muted-foreground">{{ $t('tickets.detail.resolved') }}</dt>
                <dd class="text-right">{{ formatDateTime(ticket.resolved_at) }}</dd>
              </template>
              <dt class="text-muted-foreground">{{ $t('tickets.detail.channel') }}</dt>
              <dd class="text-right">{{ $t(`tickets.channel.${ticket.channel}`) }}</dd>
            </dl>
          </div>
        </aside>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Inbox, Loader2, Lock, Send, Sparkles, Trash2, UserCheck } from 'lucide-vue-next'
import { Badge } from '@/platform/components/ui/badge'
import { Button } from '@/platform/components/ui/button'
import { Label } from '@/platform/components/ui/label'
import { Separator } from '@/platform/components/ui/separator'
import { Skeleton } from '@/platform/components/ui/skeleton'
import { Textarea } from '@/platform/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/platform/components/ui/select'
import EmptyState from '@/platform/components/common/EmptyState.vue'
import PageHeader from '@/platform/components/common/PageHeader.vue'
import PermissionGuard from '@/platform/components/common/PermissionGuard.vue'
import { cn } from '@/platform/lib/utils'
import { useConfirm } from '@/platform/composables/useConfirm'
import { useErrorHandler } from '@/platform/composables/useErrorHandler'
import { useFormatDate } from '@/platform/composables/useFormatDate'
import { usePermission } from '@/platform/composables/usePermission'
import { useToast } from '@/platform/composables/useToast'
import { useProfileStore } from '@/platform/stores/profile'
import { useUsersStore } from '@/platform/stores/users'
import type { UserOut } from '@/platform/types'
import TicketStatusBadge from '@/helpdesk/components/tickets/TicketStatusBadge.vue'
import { useTicketsStore } from '@/helpdesk/stores/tickets'
import { TICKET_PRIORITIES, TICKET_STATUSES } from '@/helpdesk/constants'
import type { AiSource, TicketPatch, TicketPriority, TicketStatus } from '@/helpdesk/types/ticket'

const UNASSIGNED = '__unassigned__'

const { t } = useI18n()
const route = useRoute('/tickets/[id]')
const router = useRouter()
const ticketsStore = useTicketsStore()
const usersStore = useUsersStore()
const profileStore = useProfileStore()
const { hasPermission } = usePermission()
const { handleError } = useErrorHandler()
const { toast } = useToast()
const { confirm } = useConfirm()
const { formatDateTime, formatRelativeTime } = useFormatDate()

const ticket = computed(() => ticketsStore.current)
const ticketId = computed(() => Number(route.params.id))
const currentUser = computed(() => profileStore.user)
const canUpdate = computed(() => hasPermission('update:ticket'))
const canAssign = computed(() => hasPermission('assign:ticket'))

const loading = ref(true)
const notFound = ref(false)

async function load() {
  loading.value = true
  notFound.value = false
  try {
    await ticketsStore.load(ticketId.value)
  } catch {
    notFound.value = true
  } finally {
    loading.value = false
  }
}

watch(ticketId, load, { immediate: true })

// Assignee picker: organization members when the user may list them; the
// current user and the current assignee are always offered.
const members = ref<UserOut[]>([])

onMounted(async () => {
  if (!canAssign.value || !hasPermission('read:user')) return
  try {
    members.value = (await usersStore.list({ page_size: 100 })).items
  } catch {
    // Non-critical: "Assign to me" and the current assignee still work.
  }
})

const assigneeOptions = computed(() => {
  const options = new Map<number, string>()
  for (const member of members.value) options.set(member.id, member.name)
  if (currentUser.value) options.set(currentUser.value.id, currentUser.value.name)
  if (ticket.value?.assignee) options.set(ticket.value.assignee.id, ticket.value.assignee.name)
  return [...options].map(([id, name]) => ({ id, name }))
})

const updating = ref(false)

async function update(patch: TicketPatch) {
  if (!ticket.value) return
  updating.value = true
  try {
    await ticketsStore.patch(ticket.value.id, patch)
    toast({ title: t('tickets.detail.updated') })
  } catch (err: unknown) {
    handleError(err)
  } finally {
    updating.value = false
  }
}

async function assign(assigneeId: number | null) {
  if (!ticket.value) return
  updating.value = true
  try {
    await ticketsStore.assign(ticket.value.id, assigneeId)
    toast({ title: t('tickets.detail.updated') })
  } catch (err: unknown) {
    handleError(err)
  } finally {
    updating.value = false
  }
}

// Composer
const mode = ref<'reply' | 'note'>('reply')
const body = ref('')
const sending = ref(false)
const isClosed = computed(() => ticket.value?.status === 'closed')

// Closed tickets only accept internal notes (the API rejects public replies).
watch(
  isClosed,
  (closed) => {
    if (closed) mode.value = 'note'
  },
  { immediate: true },
)

const composerHint = computed(() => {
  if (mode.value === 'note') {
    return isClosed.value ? t('tickets.detail.closedHint') : t('tickets.detail.noteHint')
  }
  return t('tickets.detail.replyHint', { email: ticket.value?.contact.email ?? '' })
})

async function send() {
  if (!ticket.value || !body.value.trim()) return
  const isNote = mode.value === 'note'
  sending.value = true
  try {
    await ticketsStore.reply(ticket.value.id, { body: body.value, is_internal: isNote })
    toast({ title: isNote ? t('tickets.detail.noteAdded') : t('tickets.detail.replySent') })
    body.value = ''
    draftSources.value = []
  } catch (err: unknown) {
    handleError(err)
  } finally {
    sending.value = false
  }
}

// AI reply drafts - offered only when the backend has Claude configured.
const drafting = ref(false)
const draftSources = ref<AiSource[]>([])

onMounted(() => {
  ticketsStore.loadAssistantStatus().catch(() => undefined)
})

async function draftReply() {
  if (!ticket.value) return
  if (body.value.trim()) {
    const ok = await confirm(
      t('tickets.detail.replaceDraftTitle'),
      t('tickets.detail.replaceDraftDescription'),
      t('tickets.detail.replaceDraftConfirm'),
    )
    if (!ok) return
  }
  drafting.value = true
  try {
    const suggestion = await ticketsStore.suggestReply(ticket.value.id)
    body.value = suggestion.text
    draftSources.value = suggestion.sources
  } catch (err: unknown) {
    handleError(err)
  } finally {
    drafting.value = false
  }
}

async function handleDelete() {
  if (!ticket.value) return
  const { id, number, subject } = ticket.value
  const ok = await confirm(
    t('tickets.deleteTitle'),
    t('tickets.deleteDescription', { number, subject }),
    t('common.delete'),
  )
  if (!ok) return
  try {
    await ticketsStore.remove(id)
    toast({ title: t('tickets.deleted') })
    router.push('/tickets')
  } catch (err: unknown) {
    handleError(err, t('tickets.deleteFailed'))
  }
}
</script>
