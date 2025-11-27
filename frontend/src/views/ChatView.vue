<template>
  <div class="flex h-screen bg-white">
    <!-- Left Sidebar: Conversation List -->
    <div class="w-96 border-r border-instagram-border flex flex-col">
      <!-- Header -->
      <div class="border-b border-instagram-border">
        <!-- Account Info -->
        <div class="px-6 py-3 border-b border-instagram-border">
          <div v-if="store.currentAccount" class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 via-pink-500 to-orange-500 flex items-center justify-center text-white font-semibold">
              {{ (store.currentAccount.username || '?')[0].toUpperCase() }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="font-semibold text-sm truncate">{{ store.currentAccount.username }}</div>
              <div v-if="store.currentAccount.instagram_handle" class="text-xs text-gray-500 truncate">
                @{{ store.currentAccount.instagram_handle }}
              </div>
            </div>
          </div>
          <div v-else class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-full bg-gray-200 animate-pulse"></div>
            <div class="flex-1">
              <div class="h-4 bg-gray-200 rounded animate-pulse mb-1"></div>
              <div class="h-3 bg-gray-200 rounded animate-pulse w-2/3"></div>
            </div>
          </div>
        </div>

        <!-- Messages Header -->
        <div class="h-12 flex items-center justify-between px-6">
          <h1 class="text-lg font-semibold">Messages</h1>
          <button
            @click="refreshConversations"
            class="text-instagram-blue hover:text-blue-700"
            title="Refresh"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Conversation List -->
      <ConversationList
        :conversations="store.conversations"
        :active-id="store.activeConversationId"
        :loading="store.loading"
        @select="handleSelectConversation"
      />
    </div>

    <!-- Center: Message Thread -->
    <div class="flex-1 flex flex-col">
      <MessageThread
        v-if="store.activeConversationId"
        :conversation="store.activeConversation"
        :messages="store.activeMessages"
        :loading="store.loading"
        @send="handleSendMessage"
      />
      <div v-else class="flex-1 flex items-center justify-center text-gray-400">
        <div class="text-center">
          <svg class="w-24 h-24 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <p class="text-xl">Select a conversation to start messaging</p>
        </div>
      </div>
    </div>

    <!-- Right Sidebar: Details -->
    <div class="w-80 border-l border-instagram-border">
      <ConversationDetails
        v-if="store.activeConversation"
        :conversation="store.activeConversation"
      />
    </div>

    <!-- SSE Connection Status -->
    <div
      v-if="sseError"
      class="fixed bottom-4 right-4 bg-red-500 text-white px-4 py-2 rounded-lg shadow-lg"
    >
      {{ sseError }}
    </div>
    <div
      v-else-if="sseConnected"
      class="fixed bottom-4 right-4 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg text-sm"
    >
      ✓ Real-time updates active
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useMessagesStore } from '../stores/messages'
import { useSSE } from '../composables/useSSE'
import ConversationList from '../components/ConversationList.vue'
import MessageThread from '../components/MessageThread.vue'
import ConversationDetails from '../components/ConversationDetails.vue'

const store = useMessagesStore()

// SSE connection for real-time updates
const { connected: sseConnected, error: sseError } = useSSE(
  '/api/v1/events',
  handleSSEMessage
)

function handleSSEMessage(data) {
  console.log('SSE message received:', data)

  switch (data.event) {
    case 'new_message':
      // Handle both inbound and outbound messages
      if (data.data.direction === 'inbound') {
        store.addIncomingMessage(data.data)
      } else if (data.data.direction === 'outbound') {
        // Update sent message status in real-time
        store.updateMessageStatus(data.data.id, data.data.status)
      }
      break
    case 'message_status':
      store.updateMessageStatus(data.data.message_id, data.data.status, data.data.error)
      break
    default:
      console.warn('Unknown SSE event:', data.event)
  }
}

async function handleSelectConversation(senderId) {
  store.setActiveConversation(senderId)

  // Fetch messages if not already loaded
  if (!store.messages[senderId]) {
    await store.fetchMessages(senderId)
  }
}

async function handleSendMessage(text) {
  const conversation = store.activeConversation
  if (!conversation) return

  try {
    await store.sendMessage(
      conversation.sender_id,
      text,
      conversation.instagram_account_id
    )
  } catch (err) {
    console.error('Failed to send message:', err)
    // Error is already stored in store.error
  }
}

async function refreshConversations() {
  await Promise.all([
    store.fetchCurrentAccount(),
    store.fetchConversations()
  ])
}

onMounted(async () => {
  await Promise.all([
    store.fetchCurrentAccount(),
    store.fetchConversations()
  ])
})
</script>
