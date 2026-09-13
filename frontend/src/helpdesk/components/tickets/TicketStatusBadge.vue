<template>
  <Badge :variant="variant" class="text-xs whitespace-nowrap">
    {{ $t(`tickets.status.${status}`) }}
  </Badge>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from '@/platform/components/ui/badge'
import type { TicketStatus } from '@/helpdesk/types/ticket'

const props = defineProps<{ status: TicketStatus }>()

const VARIANTS = {
  open: 'info',
  pending: 'warning',
  resolved: 'success',
  closed: 'secondary',
} as const

const variant = computed(() => VARIANTS[props.status])
</script>
