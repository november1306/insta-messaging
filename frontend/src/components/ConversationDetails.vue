<template>
  <div class="h-full overflow-y-auto custom-scrollbar">
    <!-- Header -->
    <div class="p-6 text-center border-b border-instagram-border">
      <div class="w-20 h-20 mx-auto rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white font-bold text-3xl mb-3">
        {{ getInitials(conversation?.sender_name) }}
      </div>
      <h3 class="font-semibold text-lg text-gray-900">
        {{ conversation?.sender_name || 'Unknown User' }}
      </h3>
      <p class="text-sm text-gray-500">{{ conversation?.sender_id }}</p>
    </div>

    <!-- Details -->
    <div class="p-6 space-y-6">
      <!-- Account Info -->
      <div>
        <h4 class="text-xs font-semibold text-gray-500 uppercase mb-3">Account Info</h4>
        <div class="space-y-2 text-sm">
          <div class="flex items-center gap-2">
            <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <span class="text-gray-600">{{ conversation?.sender_id }}</span>
          </div>
          <div class="flex items-center gap-2">
            <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <span class="text-gray-600">Instagram DM</span>
          </div>
        </div>
      </div>

      <!-- Stats -->
      <div>
        <h4 class="text-xs font-semibold text-gray-500 uppercase mb-3">Conversation Stats</h4>
        <div class="space-y-2 text-sm">
          <div class="flex justify-between">
            <span class="text-gray-600">Last message</span>
            <span class="font-medium">{{ formatLastMessageTime(conversation?.last_message_time) }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-600">Account</span>
            <span class="font-medium">{{ conversation?.instagram_account_id || 'N/A' }}</span>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div>
        <h4 class="text-xs font-semibold text-gray-500 uppercase mb-3">Quick Actions</h4>
        <div class="space-y-2">
          <button class="w-full px-4 py-2 text-sm text-left bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors">
            🔇 Mute conversation
          </button>
          <button class="w-full px-4 py-2 text-sm text-left bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors">
            📁 Archive
          </button>
          <button class="w-full px-4 py-2 text-sm text-left bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors">
            🏷️ Add label
          </button>
        </div>
      </div>

      <!-- Auto-Reply Status -->
      <div>
        <h4 class="text-xs font-semibold text-gray-500 uppercase mb-3">Auto-Reply</h4>
        <div class="bg-green-50 border border-green-200 rounded-lg p-3">
          <div class="flex items-center gap-2 text-sm text-green-800">
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
            </svg>
            <span class="font-medium">Rules active</span>
          </div>
          <p class="text-xs text-green-700 mt-1">Auto-reply is enabled for this conversation</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  conversation: {
    type: Object,
    default: null
  }
})

function getInitials(name) {
  if (!name) return '?'
  const parts = name.split(' ')
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase()
  }
  return name.substring(0, 2).toUpperCase()
}

function formatLastMessageTime(timestamp) {
  if (!timestamp) return 'N/A'

  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins} min ago`
  if (diffHours < 24) return `${diffHours} hours ago`
  if (diffDays < 7) return `${diffDays} days ago`

  return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
}
</script>
