<template>
  <div class="flex-1 overflow-y-auto custom-scrollbar">
    <!-- Loading State -->
    <div v-if="loading && !conversations.length" class="p-4 text-center text-gray-500">
      <svg class="animate-spin h-8 w-8 mx-auto" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <p class="mt-2">Loading conversations...</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="!conversations.length" class="p-8 text-center text-gray-500">
      <svg class="w-20 h-20 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
      <p class="font-semibold text-gray-700 mb-2">No messages yet</p>
      <p class="text-sm text-gray-500 px-4">
        Start a conversation when someone messages you. You can respond within 24 hours of their last message.
      </p>
    </div>

    <!-- Conversation Items -->
    <div v-else>
      <div
        v-for="conversation in conversations"
        :key="conversation.sender_id"
        @click="$emit('select', conversation.sender_id)"
        :class="[
          'flex items-center gap-3 p-4 border-b border-gray-100 cursor-pointer transition-colors',
          activeId === conversation.sender_id ? 'bg-instagram-bg' : 'hover:bg-gray-50'
        ]"
      >
        <!-- Avatar -->
        <div class="flex-shrink-0">
          <div class="w-14 h-14 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white font-semibold text-xl">
            {{ getInitials(conversation.sender_name) }}
          </div>
        </div>

        <!-- Conversation Info -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between mb-1">
            <h3 class="font-semibold text-gray-900 truncate">
              {{ conversation.sender_name }}
            </h3>
            <span class="text-xs text-gray-500 flex-shrink-0 ml-2">
              {{ formatTime(conversation.last_message_time) }}
            </span>
          </div>
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm text-gray-600 truncate">
              {{ conversation.last_message }}
            </p>
            <!-- Time Remaining Badge -->
            <span
              v-if="conversation.hours_remaining !== undefined && conversation.hours_remaining !== null"
              :class="[
                'text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 whitespace-nowrap',
                conversation.hours_remaining <= 2 ? 'bg-red-100 text-red-700' :
                conversation.hours_remaining <= 6 ? 'bg-orange-100 text-orange-700' :
                'bg-green-100 text-green-700'
              ]"
              :title="`You can respond for ${conversation.hours_remaining} more hour${conversation.hours_remaining !== 1 ? 's' : ''}`"
            >
              {{ conversation.hours_remaining }}h left
            </span>
          </div>
        </div>

        <!-- Unread Badge -->
        <div v-if="conversation.unread_count > 0" class="flex-shrink-0">
          <div class="bg-instagram-blue text-white text-xs font-semibold rounded-full w-6 h-6 flex items-center justify-center">
            {{ conversation.unread_count > 9 ? '9+' : conversation.unread_count }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { getInitials } from '../composables/useUserUtils'

defineProps({
  conversations: {
    type: Array,
    required: true
  },
  activeId: {
    type: String,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
})

defineEmits(['select'])

function formatTime(timestamp) {
  if (!timestamp) return ''

  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'now'
  if (diffMins < 60) return `${diffMins}m`
  if (diffHours < 24) return `${diffHours}h`
  if (diffDays < 7) return `${diffDays}d`

  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
</script>
