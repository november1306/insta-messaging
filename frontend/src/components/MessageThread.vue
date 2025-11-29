<template>
  <div class="flex flex-col h-full">
    <!-- Thread Header -->
    <div class="h-16 border-b border-instagram-border flex items-center px-6">
      <div class="flex items-center gap-3">
        <img
          v-if="conversation?.profile_picture_url"
          :src="getProxiedImageUrl(conversation.profile_picture_url)"
          :alt="conversation.sender_name"
          class="w-10 h-10 rounded-full object-cover"
        />
        <div
          v-else
          class="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white font-semibold"
        >
          {{ getInitials(conversation?.sender_name) }}
        </div>
        <div>
          <h2 class="font-semibold text-gray-900">
            {{ conversation?.sender_name }}
          </h2>
          <p class="text-xs text-gray-500">Active now</p>
        </div>
      </div>
    </div>

    <!-- Messages -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-4">
      <!-- Loading State -->
      <div v-if="loading && !messages.length" class="text-center text-gray-500 py-8">
        <svg class="animate-spin h-8 w-8 mx-auto" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <p class="mt-2">Loading messages...</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="!messages.length" class="text-center text-gray-500 py-8">
        <p>No messages yet</p>
      </div>

      <!-- Message List -->
      <div v-else>
        <MessageBubble
          v-for="message in messages"
          :key="message.id"
          :message="message"
        />
      </div>
    </div>

    <!-- Input Area -->
    <div class="border-t border-instagram-border p-4">
      <form @submit.prevent="handleSend" class="flex items-center gap-3">
        <input
          v-model="messageText"
          type="text"
          placeholder="Type a message..."
          class="flex-1 px-4 py-2 border border-instagram-border rounded-full focus:outline-none focus:border-instagram-blue"
          :disabled="sending"
        />
        <button
          type="submit"
          :disabled="!messageText.trim() || sending"
          class="px-6 py-2 bg-instagram-blue text-white rounded-full font-semibold hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {{ sending ? 'Sending...' : 'Send' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import MessageBubble from './MessageBubble.vue'
import { getInitials } from '../composables/useUserUtils'
import { getProxiedImageUrl } from '../composables/useImageProxy'

const props = defineProps({
  conversation: {
    type: Object,
    default: null
  },
  messages: {
    type: Array,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['send'])

const messageText = ref('')
const sending = ref(false)
const messagesContainer = ref(null)

async function handleSend() {
  if (!messageText.value.trim() || sending.value) return

  sending.value = true
  try {
    await emit('send', messageText.value.trim())
    messageText.value = ''
  } catch (err) {
    console.error('Failed to send message:', err)
  } finally {
    sending.value = false
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// Auto-scroll when new messages arrive
watch(() => props.messages.length, () => {
  scrollToBottom()
})

// Scroll to bottom when conversation changes
watch(() => props.conversation?.sender_id, () => {
  scrollToBottom()
})
</script>
