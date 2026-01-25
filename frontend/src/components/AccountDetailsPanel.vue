<template>
  <div class="h-full overflow-y-auto custom-scrollbar bg-gray-50">
    <!-- Header -->
    <div class="p-6 text-center border-b border-instagram-border bg-white">
      <div class="relative w-24 h-24 mx-auto mb-4">
        <img
          v-if="account.profile_picture_url"
          :src="getProxiedImageUrl(account.profile_picture_url)"
          :alt="account.username"
          class="w-24 h-24 rounded-full object-cover shadow-md"
        />
        <div
          v-else
          class="w-24 h-24 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white font-bold text-4xl shadow-md"
        >
          {{ getInitials(account.username) }}
        </div>
      </div>
      <h3 class="font-bold text-xl text-gray-900 mb-1">
        @{{ account.username }}
      </h3>
      <p class="text-sm text-gray-500">Instagram Business Account</p>
    </div>

    <!-- Details -->
    <div class="p-6 space-y-6">
      <!-- Account Info -->
      <div class="bg-white rounded-lg p-4 border border-gray-200">
        <h4 class="text-xs font-semibold text-gray-500 uppercase mb-3">Account Info</h4>
        <div class="space-y-3 text-sm">
          <div class="flex items-start gap-3">
            <svg class="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V8a2 2 0 00-2-2h-5m-4 0V5a2 2 0 114 0v1m-4 0a2 2 0 104 0m-5 8a2 2 0 100-4 2 2 0 000 4zm0 0c1.306 0 2.417.835 2.83 2M9 14a3.001 3.001 0 00-2.83 2M15 11h3m-3 4h2" />
            </svg>
            <div class="flex-1">
              <div class="text-gray-600 text-xs">Account ID</div>
              <div class="font-mono text-xs text-gray-900 break-all">{{ account.instagram_account_id }}</div>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <svg class="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <div class="flex-1">
              <div class="text-gray-600 text-xs">Messaging Channel</div>
              <div class="font-mono text-xs text-gray-900 break-all">{{ account.messaging_channel_id }}</div>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <svg class="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div class="flex-1">
              <div class="text-gray-600 text-xs">Linked</div>
              <div class="text-gray-900">{{ formatDate(account.created_at) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- CRM Integration -->
      <div v-if="account.crm_webhook_url" class="bg-white rounded-lg p-4 border border-gray-200">
        <h4 class="text-xs font-semibold text-gray-500 uppercase mb-3">CRM Integration</h4>
        <div class="bg-green-50 border border-green-200 rounded-lg p-3">
          <div class="flex items-center gap-2 text-sm text-green-800">
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
            </svg>
            <span class="font-medium">Webhook Active</span>
          </div>
          <p class="text-xs text-green-700 mt-2">Messages are forwarded to your CRM</p>
        </div>
      </div>

      <!-- Danger Zone -->
      <div class="bg-white rounded-lg p-4 border border-red-200">
        <h4 class="text-xs font-semibold text-red-600 uppercase mb-3 flex items-center gap-2">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          Danger Zone
        </h4>

        <div class="space-y-3">
          <!-- Unlink Button -->
          <button
            @click="$emit('unlink')"
            class="w-full px-4 py-2.5 text-sm font-medium text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-300 rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
            </svg>
            Unlink Account
          </button>
          <p class="text-xs text-gray-500 px-1">
            Removes this account from your view without deleting data
          </p>

          <!-- Delete Button -->
          <div class="pt-3 border-t border-red-200">
            <button
              @click="$emit('delete')"
              class="w-full px-4 py-3 text-sm font-semibold text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors flex items-center justify-center gap-2 shadow-sm"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Delete Permanently
            </button>
            <div class="mt-3 bg-red-50 border border-red-200 rounded-lg p-3">
              <p class="text-xs text-red-800 font-medium flex items-start gap-2">
                <svg class="w-4 h-4 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                </svg>
                <span>This will permanently delete all conversations, messages, media files, and CRM data for this account. This action cannot be undone.</span>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { getInitials } from '../composables/useUserUtils'
import { getProxiedImageUrl } from '../composables/useImageProxy'

defineProps({
  account: {
    type: Object,
    required: true
  }
})

defineEmits(['unlink', 'delete'])

function formatDate(timestamp) {
  if (!timestamp) return 'N/A'

  const date = new Date(timestamp)
  return date.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric'
  })
}
</script>

<style scoped>
/* Custom scrollbar */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 3px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
</style>
