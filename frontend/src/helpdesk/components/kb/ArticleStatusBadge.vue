<template>
  <Badge
    :variant="status === 'published' ? 'success' : 'secondary'"
    class="text-xs whitespace-nowrap"
  >
    {{ $t(`kb.status.${status}`) }}
  </Badge>
</template>

<script setup lang="ts">
import { Badge } from '@/platform/components/ui/badge'
import type { ArticleStatus } from '@/helpdesk/types/kb'

defineProps<{ status: ArticleStatus }>()
</script>
