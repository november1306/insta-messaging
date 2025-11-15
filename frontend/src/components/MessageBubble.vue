<template>
  <div :class="['flex', isOutbound ? 'justify-end' : 'justify-start']">
    <div :class="['max-w-md px-4 py-2 rounded-2xl', bubbleClasses]">
      <p class="text-sm whitespace-pre-wrap break-words">{{ message.text }}</p>
      <div :class="['flex items-center gap-1 mt-1 text-xs', timeClasses]">
        <span>{{ formatTime(message.timestamp) }}</span>
        <span v-if="isOutbound && message.status" class="ml-1">
          {{ statusIcon }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  message: {
    type: Object,
    required: true
  }
})

const isOutbound = computed(() => props.message.direction === 'outbound')

const bubbleClasses = computed(() => {
  if (isOutbound.value) {
    return 'bg-instagram-blue text-white'
  }
  return 'bg-gray-100 text-gray-900'
})

const timeClasses = computed(() => {
  if (isOutbound.value) {
    return 'text-blue-100'
  }
  return 'text-gray-500'
})

const statusIcon = computed(() => {
  switch (props.message.status) {
    case 'sent':
      return '✓'
    case 'delivered':
      return '✓✓'
    case 'read':
      return '✓✓'
    case 'failed':
      return '✗'
    default:
      return '○'
  }
})

function formatTime(timestamp) {
  if (!timestamp) return ''

  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  })
}
</script>
