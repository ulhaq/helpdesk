<template>
  <Badge :variant="variant" class="text-xs whitespace-nowrap">
    {{ $t(`tickets.priority.${priority}`) }}
  </Badge>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from '@/platform/components/ui/badge'
import type { TicketPriority } from '@/helpdesk/types/ticket'

const props = defineProps<{ priority: TicketPriority }>()

const VARIANTS = {
  low: 'outline',
  normal: 'secondary',
  high: 'warning',
  urgent: 'error',
} as const

const variant = computed(() => VARIANTS[props.priority])
</script>
