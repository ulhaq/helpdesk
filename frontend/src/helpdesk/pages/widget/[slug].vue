<route lang="yaml">
meta:
  layout: bare
  public: true
</route>

<template>
  <div class="flex h-screen flex-col">
    <header class="shrink-0 px-5 py-4" :style="brandStyle">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="truncate text-sm opacity-80">{{ config?.organization_name }}</p>
          <h1 class="text-lg font-semibold leading-snug">
            {{ config?.greeting || $t('widget.defaultGreeting') }}
          </h1>
        </div>
        <button
          v-if="isEmbedded"
          type="button"
          class="rounded-md p-1 opacity-80 hover:opacity-100 focus-visible:outline focus-visible:outline-2"
          :aria-label="$t('widget.close')"
          @click="closeWidget"
        >
          <X class="h-5 w-5" />
        </button>
      </div>
    </header>

    <div class="min-h-0 flex-1 overflow-y-auto">
      <div v-if="state === 'loading'" class="space-y-3 p-5">
        <Skeleton class="h-10 w-full" />
        <Skeleton class="h-24 w-full" />
      </div>

      <p v-else-if="state === 'unavailable'" class="p-5 text-center text-sm text-muted-foreground">
        {{ $t('widget.unavailable') }}
      </p>

      <!-- Home -->
      <div v-else-if="view === 'home'" class="space-y-5 p-5">
        <form
          v-if="config?.help_center_enabled"
          role="search"
          class="space-y-2"
          @submit.prevent="searchArticles"
        >
          <Label for="widget-article-search">{{ $t('widget.searchArticles') }}</Label>
          <div class="flex gap-2">
            <Input
              id="widget-article-search"
              v-model="articleQuery"
              type="search"
              :placeholder="$t('widget.searchPlaceholder')"
            />
            <Button
              type="submit"
              variant="outline"
              class="shrink-0 px-3"
              :aria-label="$t('widget.searchArticles')"
              :disabled="searchingArticles"
            >
              <Search class="h-4 w-4" />
            </Button>
          </div>
          <p v-if="articleResults && !articleResults.length" class="text-sm text-muted-foreground">
            {{ $t('widget.noArticles') }}
          </p>
          <ul v-else-if="articleResults" class="divide-y rounded-lg border">
            <li v-for="article in articleResults" :key="article.slug">
              <button
                type="button"
                class="block w-full px-4 py-3 text-left hover:bg-muted/50"
                @click="openArticle(article.slug)"
              >
                <span class="block text-sm font-medium">{{ article.title }}</span>
                <span
                  v-if="article.excerpt"
                  class="mt-0.5 line-clamp-2 block text-xs text-muted-foreground"
                >
                  {{ article.excerpt }}
                </span>
              </button>
            </li>
          </ul>
        </form>

        <Button class="w-full" :style="brandStyle" @click="startConversation">
          <MessageSquarePlus class="mr-2 h-4 w-4" />
          {{ $t('widget.startConversation') }}
        </Button>

        <section v-if="widgetStore.tickets.length" class="space-y-2">
          <h2 class="text-sm font-medium text-muted-foreground">
            {{ $t('widget.yourConversations') }}
          </h2>
          <ul class="divide-y rounded-lg border">
            <li v-for="ticket in widgetStore.tickets" :key="ticket.id">
              <button
                type="button"
                class="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-muted/50"
                @click="showTicket(ticket.id)"
              >
                <span class="min-w-0">
                  <span class="block truncate text-sm font-medium">{{ ticket.subject }}</span>
                  <span class="block text-xs text-muted-foreground">
                    {{ $t('widget.ticketNumber', { number: ticket.number }) }} ·
                    {{ formatRelativeTime(ticket.last_message_at) }}
                  </span>
                </span>
                <Badge :variant="STATUS_VARIANTS[ticket.status]" class="shrink-0 text-xs">
                  {{ $t(`widget.status.${ticket.status}`) }}
                </Badge>
              </button>
            </li>
          </ul>
        </section>

        <button
          v-if="widgetStore.canFindConversations"
          type="button"
          class="text-sm text-muted-foreground underline-offset-4 hover:underline"
          @click="view = 'access'"
        >
          {{ $t('widget.findConversations') }}
        </button>
      </div>

      <!-- New conversation -->
      <form
        v-else-if="view === 'new'"
        class="space-y-4 p-5"
        novalidate
        @submit.prevent="submitTicket"
      >
        <BackLink @click="goHome" />
        <div class="grid gap-4 sm:grid-cols-2">
          <div class="space-y-1.5">
            <Label for="widget-name">{{ $t('widget.form.name') }}</Label>
            <Input
              id="widget-name"
              v-model="ticketForm.form.name"
              autocomplete="name"
              :disabled="sending"
            />
            <p v-if="ticketForm.errors.name" class="text-xs text-destructive">
              {{ ticketForm.errors.name }}
            </p>
          </div>
          <div class="space-y-1.5">
            <Label for="widget-email">{{ $t('widget.form.email') }}</Label>
            <Input
              id="widget-email"
              v-model="ticketForm.form.email"
              type="email"
              autocomplete="email"
              :disabled="sending"
            />
            <p v-if="ticketForm.errors.email" class="text-xs text-destructive">
              {{ ticketForm.errors.email }}
            </p>
          </div>
        </div>
        <div class="space-y-1.5">
          <Label for="widget-subject">{{ $t('widget.form.subject') }}</Label>
          <Input id="widget-subject" v-model="ticketForm.form.subject" :disabled="sending" />
          <p v-if="ticketForm.errors.subject" class="text-xs text-destructive">
            {{ ticketForm.errors.subject }}
          </p>
        </div>
        <div class="space-y-1.5">
          <Label for="widget-body">{{ $t('widget.form.body') }}</Label>
          <Textarea
            id="widget-body"
            v-model="ticketForm.form.body"
            rows="5"
            :placeholder="$t('widget.form.bodyPlaceholder')"
            :disabled="sending"
          />
          <p v-if="ticketForm.errors.body" class="text-xs text-destructive">
            {{ ticketForm.errors.body }}
          </p>
        </div>
        <p v-if="formError" class="text-sm text-destructive" role="alert">{{ formError }}</p>
        <Button type="submit" class="w-full" :style="brandStyle" :disabled="sending">
          <Loader2 v-if="sending" class="mr-2 h-4 w-4 animate-spin" />
          {{ $t('widget.form.submit') }}
        </Button>
      </form>

      <!-- Conversation -->
      <div v-else-if="view === 'ticket' && widgetStore.current" class="flex min-h-full flex-col">
        <div class="space-y-1 border-b px-5 py-3">
          <BackLink @click="goHome" />
          <h2 class="font-semibold leading-snug">{{ widgetStore.current.subject }}</h2>
          <p class="text-xs text-muted-foreground">
            {{ $t('widget.ticketNumber', { number: widgetStore.current.number }) }} ·
            {{ $t(`widget.status.${widgetStore.current.status}`) }}
          </p>
        </div>

        <p v-if="justCreated" class="mx-5 mt-4 rounded-md bg-muted px-3 py-2 text-sm" role="status">
          {{ $t('widget.createdNotice') }}
        </p>

        <ol class="flex-1 space-y-3 p-5" aria-live="polite">
          <li
            v-for="message in widgetStore.current.messages"
            :key="message.id"
            :class="cn('flex', message.author_type === 'contact' ? 'justify-end' : 'justify-start')"
          >
            <div
              :class="
                cn(
                  'max-w-[85%] rounded-2xl px-4 py-2 text-sm',
                  message.author_type === 'contact' ? 'rounded-br-sm' : 'rounded-bl-sm bg-muted',
                )
              "
              :style="message.author_type === 'contact' ? brandStyle : undefined"
            >
              <p
                v-if="message.author_type === 'agent'"
                class="mb-0.5 text-xs font-medium opacity-70"
              >
                {{ message.author_name }}
              </p>
              <p class="whitespace-pre-wrap break-words">{{ message.body }}</p>
              <p class="mt-1 text-[11px] opacity-70">
                {{ formatRelativeTime(message.created_at) }}
              </p>
            </div>
          </li>
        </ol>

        <p
          v-if="widgetStore.current.status === 'closed'"
          class="border-t p-4 text-center text-xs text-muted-foreground"
        >
          {{ $t('widget.closedHint') }}
        </p>
        <form
          v-else
          class="sticky bottom-0 space-y-2 border-t bg-background p-3"
          @submit.prevent="sendReply"
        >
          <Textarea
            v-model="replyBody"
            rows="3"
            :aria-label="$t('widget.replyLabel')"
            :placeholder="$t('widget.replyPlaceholder')"
            :disabled="sending"
          />
          <div class="flex justify-end">
            <Button
              type="submit"
              size="sm"
              :style="brandStyle"
              :disabled="sending || !replyBody.trim()"
            >
              <Loader2 v-if="sending" class="mr-2 h-4 w-4 animate-spin" />
              <Send v-else class="mr-2 h-4 w-4" />
              {{ $t('widget.send') }}
            </Button>
          </div>
        </form>
      </div>

      <!-- Help article -->
      <div v-else-if="view === 'article' && currentArticle" class="space-y-4 p-5">
        <BackLink @click="goHome" />
        <h2 class="text-lg font-semibold leading-snug">{{ currentArticle.title }}</h2>
        <MarkdownContent :html="currentArticle.html" />
        <div class="space-y-3 border-t pt-4">
          <a
            :href="helpArticleUrl(currentArticle.slug)"
            target="_blank"
            rel="noopener"
            class="block text-sm text-muted-foreground underline-offset-4 hover:underline"
          >
            {{ $t('widget.openInHelpCenter') }}
          </a>
          <p class="text-sm font-medium">{{ $t('widget.stillNeedHelp') }}</p>
          <Button class="w-full" :style="brandStyle" @click="startConversation">
            <MessageSquarePlus class="mr-2 h-4 w-4" />
            {{ $t('widget.startConversation') }}
          </Button>
        </div>
      </div>

      <!-- Find earlier conversations -->
      <form
        v-else-if="view === 'access'"
        class="space-y-4 p-5"
        novalidate
        @submit.prevent="requestAccess"
      >
        <BackLink @click="goHome" />
        <div class="space-y-1">
          <h2 class="font-semibold">{{ $t('widget.access.title') }}</h2>
          <p class="text-sm text-muted-foreground">{{ $t('widget.access.description') }}</p>
        </div>
        <p v-if="accessSent" class="rounded-md bg-muted px-3 py-2 text-sm" role="status">
          {{ $t('widget.access.sent') }}
        </p>
        <template v-else>
          <div class="space-y-1.5">
            <Label for="widget-access-email">{{ $t('widget.form.email') }}</Label>
            <Input
              id="widget-access-email"
              v-model="accessForm.form.email"
              type="email"
              autocomplete="email"
              :disabled="sending"
            />
            <p v-if="accessForm.errors.email" class="text-xs text-destructive">
              {{ accessForm.errors.email }}
            </p>
          </div>
          <p v-if="formError" class="text-sm text-destructive" role="alert">{{ formError }}</p>
          <Button type="submit" class="w-full" :style="brandStyle" :disabled="sending">
            <Loader2 v-if="sending" class="mr-2 h-4 w-4 animate-spin" />
            {{ $t('widget.access.submit') }}
          </Button>
        </template>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Loader2, MessageSquarePlus, Search, Send, X } from 'lucide-vue-next'
import { Badge } from '@/platform/components/ui/badge'
import { Button } from '@/platform/components/ui/button'
import { Input } from '@/platform/components/ui/input'
import { Label } from '@/platform/components/ui/label'
import { Skeleton } from '@/platform/components/ui/skeleton'
import { Textarea } from '@/platform/components/ui/textarea'
import { cn } from '@/platform/lib/utils'
import { useErrorHandler } from '@/platform/composables/useErrorHandler'
import { useFormatDate } from '@/platform/composables/useFormatDate'
import { useRules } from '@/platform/composables/useRules'
import { useValidation } from '@/platform/composables/useValidation'
import { LOCALE_ORDER, type SupportedLocale } from '@/plugins/i18n'
import MarkdownContent from '@/helpdesk/components/kb/MarkdownContent.vue'
import { useHelpCenterStore } from '@/helpdesk/stores/helpCenter'
import { useWidgetStore } from '@/helpdesk/stores/widget'
import type { HelpArticle, HelpArticleSummary } from '@/helpdesk/types/kb'
import { brandColors } from '@/helpdesk/utils/brand'

type View = 'home' | 'new' | 'ticket' | 'access' | 'article'

const STATUS_VARIANTS = {
  open: 'info',
  pending: 'warning',
  resolved: 'success',
  closed: 'secondary',
} as const

const { t, locale } = useI18n()
const route = useRoute('/widget/[slug]')
const router = useRouter()
const widgetStore = useWidgetStore()
const { formatRelativeTime } = useFormatDate()
const { resolveError, handleError } = useErrorHandler()
const rules = useRules()

const BackLink = defineComponent({
  emits: ['click'],
  setup(_, { emit }) {
    return () =>
      h(
        'button',
        {
          type: 'button',
          class:
            'inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground',
          onClick: () => emit('click'),
        },
        [h(ArrowLeft, { class: 'h-4 w-4' }), t('widget.back')],
      )
  },
})

const state = ref<'loading' | 'ready' | 'unavailable'>('loading')
const view = ref<View>('home')
const config = computed(() => widgetStore.config)
const isEmbedded = typeof window !== 'undefined' && window.parent !== window

const brandStyle = computed(() => brandColors(config.value?.brand_color))

const currentLocale = () => locale.value as SupportedLocale

onMounted(async () => {
  const lang = route.query.lang
  if (typeof lang === 'string' && (LOCALE_ORDER as string[]).includes(lang)) {
    locale.value = lang
  }

  try {
    await widgetStore.init(route.params.slug)
  } catch {
    state.value = 'unavailable'
    return
  }

  const token = route.query.token
  if (typeof token === 'string' && token) {
    widgetStore.acceptContactToken(token)
    // Keep the token out of the address bar and browser history.
    const { token: _token, ...query } = route.query
    router.replace({ name: '/widget/[slug]', params: { slug: route.params.slug }, query })
  }

  try {
    await widgetStore.loadTickets()
  } catch {
    // The conversation list is a convenience; starting a new one still works.
  }
  state.value = 'ready'
})

const sending = ref(false)
const formError = ref('')
const justCreated = ref(false)

function goHome() {
  view.value = 'home'
  formError.value = ''
  accessSent.value = false
}

function startConversation() {
  formError.value = ''
  ticketForm.clearErrors()
  view.value = 'new'
}

const ticketForm = useValidation({
  name: rules.required,
  email: rules.email,
  subject: rules.required,
  body: rules.required,
})

async function submitTicket() {
  if (!ticketForm.validate()) return
  sending.value = true
  formError.value = ''
  try {
    await widgetStore.createTicket({
      name: ticketForm.form.name,
      email: ticketForm.form.email,
      subject: ticketForm.form.subject,
      body: ticketForm.form.body,
      locale: currentLocale(),
    })
    ticketForm.form.subject = ''
    ticketForm.form.body = ''
    justCreated.value = true
    view.value = 'ticket'
    widgetStore.loadTickets().catch(() => undefined)
  } catch (err: unknown) {
    formError.value = resolveError(err)
  } finally {
    sending.value = false
  }
}

async function showTicket(id: number) {
  justCreated.value = false
  try {
    await widgetStore.openTicket(id)
    view.value = 'ticket'
  } catch (err: unknown) {
    handleError(err)
  }
}

const replyBody = ref('')

async function sendReply() {
  if (!replyBody.value.trim()) return
  sending.value = true
  try {
    await widgetStore.reply(replyBody.value)
    replyBody.value = ''
    justCreated.value = false
  } catch (err: unknown) {
    handleError(err)
  } finally {
    sending.value = false
  }
}

const accessForm = useValidation({ email: rules.email })
const accessSent = ref(false)

async function requestAccess() {
  if (!accessForm.validate()) return
  sending.value = true
  formError.value = ''
  try {
    await widgetStore.requestAccessLink(accessForm.form.email, currentLocale())
    accessSent.value = true
  } catch (err: unknown) {
    formError.value = resolveError(err)
  } finally {
    sending.value = false
  }
}

const helpCenterStore = useHelpCenterStore()
const articleQuery = ref('')
const articleResults = ref<HelpArticleSummary[] | null>(null)
const currentArticle = ref<HelpArticle | null>(null)
const searchingArticles = ref(false)

async function searchArticles() {
  const q = articleQuery.value.trim()
  if (!q) {
    articleResults.value = null
    return
  }
  searchingArticles.value = true
  try {
    const { articles } = await helpCenterStore.search(route.params.slug, { q })
    articleResults.value = articles.slice(0, 5)
  } catch (err: unknown) {
    handleError(err)
  } finally {
    searchingArticles.value = false
  }
}

async function openArticle(articleSlug: string) {
  try {
    currentArticle.value = await helpCenterStore.article(route.params.slug, articleSlug)
    view.value = 'article'
  } catch (err: unknown) {
    handleError(err)
  }
}

function helpArticleUrl(articleSlug: string): string {
  return router.resolve({
    name: '/help/[slug]/articles/[article]',
    params: { slug: route.params.slug, article: articleSlug },
  }).href
}

function closeWidget() {
  window.parent.postMessage({ type: 'helpdesk:close' }, '*')
}
</script>
