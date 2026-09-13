<route lang="yaml">
meta:
  layout: dashboard
  requiresAuth: true
  permission: manage:helpdesk
  breadcrumb: nav.supportSite
</route>

<template>
  <div class="animate-fade-in space-y-6">
    <PageHeader :title="$t('supportSite.title')" :description="$t('supportSite.description')">
      <template #actions>
        <Button v-if="site?.help_center_enabled" variant="outline" size="sm" as-child>
          <a :href="helpCenterUrl" target="_blank" rel="noopener">
            <BookOpen class="w-4 h-4 mr-2" />
            {{ $t('supportSite.openHelpCenter') }}
          </a>
        </Button>
        <Button v-if="site?.widget_enabled" variant="outline" size="sm" as-child>
          <a :href="widgetUrl" target="_blank" rel="noopener">
            <ExternalLink class="w-4 h-4 mr-2" />
            {{ $t('supportSite.preview') }}
          </a>
        </Button>
      </template>
    </PageHeader>

    <Skeleton v-if="loading" class="h-72 w-full" />

    <template v-else-if="site">
      <Card>
        <CardHeader>
          <CardTitle>{{ $t('supportSite.settingsTitle') }}</CardTitle>
        </CardHeader>
        <CardContent>
          <form class="max-w-xl space-y-5" @submit.prevent="save">
            <div class="space-y-2">
              <Label for="support-slug">{{ $t('supportSite.slug') }}</Label>
              <div
                class="flex items-center rounded-md border focus-within:ring-1 focus-within:ring-ring"
              >
                <span class="hidden select-none pl-3 text-sm text-muted-foreground sm:inline">
                  {{ origin }}/widget/
                </span>
                <Input
                  id="support-slug"
                  v-model="form.slug"
                  class="border-0 shadow-none focus-visible:ring-0"
                  autocomplete="off"
                  :disabled="saving"
                />
              </div>
              <p class="text-xs text-muted-foreground">{{ $t('supportSite.slugHint') }}</p>
            </div>

            <div class="space-y-2">
              <Label for="support-color">{{ $t('supportSite.brandColor') }}</Label>
              <div class="flex items-center gap-2">
                <input
                  v-model="form.brandColor"
                  type="color"
                  class="h-9 w-12 cursor-pointer rounded-md border bg-transparent p-1"
                  :aria-label="$t('supportSite.brandColor')"
                  :disabled="saving"
                />
                <Input
                  id="support-color"
                  v-model="form.brandColor"
                  class="w-32 font-mono"
                  maxlength="7"
                  :disabled="saving"
                />
              </div>
            </div>

            <div class="space-y-2">
              <Label for="support-greeting">
                {{ $t('supportSite.greeting') }}
                <span class="text-muted-foreground">({{ $t('common.optional') }})</span>
              </Label>
              <Input
                id="support-greeting"
                v-model="form.greeting"
                maxlength="255"
                :placeholder="$t('widget.defaultGreeting')"
                :disabled="saving"
              />
            </div>

            <div class="flex items-start gap-3">
              <Checkbox
                id="support-enabled"
                class="mt-0.5"
                :model-value="form.enabled"
                :disabled="saving"
                @update:model-value="(value) => (form.enabled = value === true)"
              />
              <div class="space-y-1">
                <Label for="support-enabled">{{ $t('supportSite.enabled') }}</Label>
                <p class="text-xs text-muted-foreground">{{ $t('supportSite.enabledHint') }}</p>
              </div>
            </div>

            <div class="flex items-start gap-3">
              <Checkbox
                id="support-help-center"
                class="mt-0.5"
                :model-value="form.helpCenterEnabled"
                :disabled="saving"
                @update:model-value="(value) => (form.helpCenterEnabled = value === true)"
              />
              <div class="space-y-1">
                <Label for="support-help-center">{{ $t('supportSite.helpCenterEnabled') }}</Label>
                <p class="text-xs text-muted-foreground">{{ $t('supportSite.helpCenterHint') }}</p>
              </div>
            </div>

            <p v-if="errorMessage" class="text-sm text-destructive" role="alert">
              {{ errorMessage }}
            </p>

            <Button type="submit" :disabled="saving || !isDirty">
              <Loader2 v-if="saving" class="w-4 h-4 mr-2 animate-spin" />
              {{ $t('common.saveChanges') }}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{{ $t('supportSite.installTitle') }}</CardTitle>
          <CardDescription>{{ $t('supportSite.installDescription') }}</CardDescription>
        </CardHeader>
        <CardContent class="space-y-3">
          <pre
            class="overflow-x-auto rounded-md bg-muted p-4 text-xs"
          ><code>{{ snippet }}</code></pre>
          <Button variant="outline" size="sm" @click="copySnippet">
            <Check v-if="copied" class="w-4 h-4 mr-2" />
            <Copy v-else class="w-4 h-4 mr-2" />
            {{ copied ? $t('supportSite.copied') : $t('supportSite.copy') }}
          </Button>
        </CardContent>
      </Card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { BookOpen, Check, Copy, ExternalLink, Loader2 } from 'lucide-vue-next'
import { BRAND } from '@/brand'
import { Button } from '@/platform/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/platform/components/ui/card'
import { Checkbox } from '@/platform/components/ui/checkbox'
import { Input } from '@/platform/components/ui/input'
import { Label } from '@/platform/components/ui/label'
import { Skeleton } from '@/platform/components/ui/skeleton'
import PageHeader from '@/platform/components/common/PageHeader.vue'
import { useErrorHandler } from '@/platform/composables/useErrorHandler'
import { useToast } from '@/platform/composables/useToast'
import { useSupportSiteStore } from '@/helpdesk/stores/supportSite'
import type { SupportSite } from '@/helpdesk/types/supportSite'

const { t } = useI18n()
const { toast } = useToast()
const { handleError, resolveError, resolveFieldErrors } = useErrorHandler()
const supportSiteStore = useSupportSiteStore()

const site = computed(() => supportSiteStore.site)
const loading = ref(true)
const saving = ref(false)
const errorMessage = ref('')
const form = reactive({
  slug: '',
  brandColor: '',
  greeting: '',
  enabled: true,
  helpCenterEnabled: true,
})

// The widget is served by this app, so embeds point at the origin agents use.
const origin = typeof window !== 'undefined' ? window.location.origin : BRAND.appOrigin
const widgetUrl = computed(() => `${origin}/widget/${site.value?.slug ?? ''}`)
const helpCenterUrl = computed(() => `${origin}/help/${site.value?.slug ?? ''}`)
// Split closing tag: a literal one would end this <script setup> block.
const snippet = computed(
  () =>
    `<script src="${origin}/widget.js" data-site="${site.value?.slug ?? ''}" async></` + 'script>',
)

function resetForm(value: SupportSite) {
  form.slug = value.slug
  form.brandColor = value.brand_color
  form.greeting = value.greeting ?? ''
  form.enabled = value.widget_enabled
  form.helpCenterEnabled = value.help_center_enabled
}

onMounted(async () => {
  try {
    resetForm(await supportSiteStore.load())
  } catch (err: unknown) {
    handleError(err)
  } finally {
    loading.value = false
  }
})

const isDirty = computed(() => {
  const current = site.value
  if (!current) return false
  return (
    form.slug.trim() !== current.slug ||
    form.brandColor.toLowerCase() !== current.brand_color ||
    (form.greeting.trim() || null) !== current.greeting ||
    form.enabled !== current.widget_enabled ||
    form.helpCenterEnabled !== current.help_center_enabled
  )
})

async function save() {
  saving.value = true
  errorMessage.value = ''
  try {
    const updated = await supportSiteStore.patch({
      slug: form.slug.trim(),
      brand_color: form.brandColor,
      greeting: form.greeting.trim() || null,
      widget_enabled: form.enabled,
      help_center_enabled: form.helpCenterEnabled,
    })
    resetForm(updated)
    toast({ title: t('supportSite.saved') })
  } catch (err: unknown) {
    const fieldErrors = resolveFieldErrors(err)
    errorMessage.value =
      fieldErrors['body__slug'] ?? fieldErrors['body__brand_color'] ?? resolveError(err)
  } finally {
    saving.value = false
  }
}

const copied = ref(false)

async function copySnippet() {
  try {
    await navigator.clipboard.writeText(snippet.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch (err: unknown) {
    handleError(err)
  }
}
</script>
