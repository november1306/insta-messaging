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
      <svg class="w-16 h-16 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
      </svg>
      <p>No conversations yet</p>
      <p class="text-sm mt-2">Messages will appear here when customers reach out</p>
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
              {{ conversation.sender_name || conversation.sender_id }}
            </h3>
            <span class="text-xs text-gray-500 flex-shrink-0 ml-2">
              {{ formatTime(conversation.last_message_time) }}
            </span>
          </div>
          <p class="text-sm text-gray-600 truncate">
            {{ conversation.last_message }}
          </p>
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

function getInitials(name) {
  if (!name) return '?'
  const parts = name.split(' ')
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase()
  }
  return name.substring(0, 2).toUpperCase()
}

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
