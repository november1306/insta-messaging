<template>
  <div class="flex h-screen bg-white">
    <!-- Left Sidebar: Account Selector (Master Account + Instagram Accounts) -->
    <div class="w-72 border-r border-instagram-border">
      <AccountSelector :sse-connected="sseConnected" :sse-error="sseError" />
    </div>

    <!-- Center: Conversation List (Contacts for Selected Instagram Account) -->
    <div class="w-96 border-r border-instagram-border flex flex-col">
      <!-- Contacts Header -->
      <div class="border-b border-instagram-border bg-white">
        <!-- Active Instagram Account Header -->
        <div v-if="accountsStore.selectedAccount" class="px-6 py-4 border-b border-instagram-border">
          <div class="flex items-center gap-3">
            <img
              v-if="accountsStore.selectedAccount.profile_picture_url"
              :src="getProxiedImageUrl(accountsStore.selectedAccount.profile_picture_url)"
              :alt="accountsStore.selectedAccount.username"
              class="w-10 h-10 rounded-full object-cover shadow-sm"
            />
            <div
              v-else
              class="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 via-pink-500 to-orange-500 flex items-center justify-center text-white font-bold shadow-sm"
            >
              {{ getAccountInitial(accountsStore.selectedAccount.username) }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="font-semibold text-sm truncate">@{{ accountsStore.selectedAccount.username }}</div>
              <div class="text-xs text-gray-500 truncate">Active Instagram account</div>
            </div>
          </div>
        </div>
        <div v-else class="px-6 py-4 border-b border-instagram-border">
          <div class="text-sm text-gray-500 text-center">No Instagram account selected</div>
        </div>

        <!-- Messages Header -->
        <div class="h-14 flex items-center justify-between px-6">
          <h1 class="text-xl font-bold">Contacts</h1>
          <button
            @click="refreshConversations"
            class="text-instagram-blue hover:text-blue-700 transition-colors p-2 hover:bg-gray-50 rounded-full"
            title="Refresh conversations"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Conversation List -->
      <ConversationList
        :conversations="filteredConversations"
        :active-id="store.activeConversationId"
        :loading="store.loading"
        @select="handleSelectConversation"
      />
    </div>

    <!-- Right: Message Thread -->
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
  </div>
</template>

<script setup>
import { onMounted, ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useMessagesStore } from '../stores/messages'
import { useSessionStore } from '../stores/session'
import { useAccountsStore } from '../stores/accounts'
import { useSSE } from '../composables/useSSE'
import { getProxiedImageUrl } from '../composables/useImageProxy'
import apiClient from '../api/client'
import ConversationList from '../components/ConversationList.vue'
import MessageThread from '../components/MessageThread.vue'
import AccountSelector from '../components/AccountSelector.vue'

const router = useRouter()
const store = useMessagesStore()
const sessionStore = useSessionStore()
const accountsStore = useAccountsStore()

// Filter conversations by selected messaging channel
const filteredConversations = computed(() => {
  if (!accountsStore.selectedAccount) {
    return []
  }

  // Filter conversations where the messaging_channel_id matches selected account's channel
  return store.conversations.filter(conversation => {
    // Conversations have messaging_channel_id which is the unique channel that received the message
    return conversation.messaging_channel_id === accountsStore.selectedAccount.messaging_channel_id
  })
})

// Watch for account changes and refresh conversations
watch(
  () => accountsStore.selectedAccountId,
  async (newAccountId, oldAccountId) => {
    if (newAccountId && newAccountId !== oldAccountId) {
      await refreshConversations()
    }
  }
)

// SSE connection for real-time updates
const { connected: sseConnected, error: sseError } = useSSE(
  '/api/v1/events',
  handleSSEMessage
)

function handleSSEMessage(data) {
  switch (data.event) {
    case 'new_message':
      // Handle both inbound and outbound messages
      if (data.data.direction === 'inbound') {
        store.addIncomingMessage(data.data)
      } else if (data.data.direction === 'outbound') {
        // For outbound messages from SSE, check if message already exists (optimistic update)
        // If it exists, update it with full data including attachments
        // If not, add it (e.g., message sent from other session/tab)
        const recipientId = data.data.recipient_id  // Customer ID (not business account)

        // Initialize conversation array if needed
        if (!store.messages[recipientId]) {
          store.messages[recipientId] = []
        }

        // Multi-strategy matching to handle race conditions:
        // 1. Match by Instagram message ID (if already updated)
        // 2. Match by tracking_message_id (from API response)
        // 3. Match by tempId (if SSE arrives before API response)
        // 4. Match by content (timestamp + text + status=pending as fallback)

        let existingIndex = store.messages[recipientId].findIndex(m => {
          // Strategy 1: Instagram ID match
          if (m.id === data.data.id) return true

          // Strategy 2: Tracking ID match (optimistic message updated by API)
          if (data.data.tracking_message_id && (m.id === data.data.tracking_message_id || m.trackingId === data.data.tracking_message_id)) return true

          // Strategy 3: Temp ID match (SSE arrived before API response)
          if (m.tempId && data.data.tracking_message_id && m.tempId.startsWith('temp_')) return true

          // Strategy 4: Content-based fallback (pending message with same text in last 10 seconds)
          if (m.status === 'pending' && m.text === data.data.text && m.recipientId === recipientId) {
            const timeDiff = Math.abs(new Date(m.timestamp) - new Date(data.data.timestamp))
            if (timeDiff < 10000) return true  // Within 10 seconds
          }

          return false
        })

        if (existingIndex >= 0) {
          // IMPORTANT: Update ONLY the status and ID, preserve optimistic data
          const existingMsg = store.messages[recipientId][existingIndex]

          console.log('[SSE] Updating existing outbound message:', {
            existingId: existingMsg.id,
            tempId: existingMsg.tempId,
            sseId: data.data.id,
            sseTrackingId: data.data.tracking_message_id
          })

          // Update with SSE data but keep tempId for future matching
          store.messages[recipientId][existingIndex] = {
            ...existingMsg,  // Keep existing data (including tempId)
            id: data.data.id,  // Update to Instagram message ID
            status: data.data.status || 'sent',  // Update status marker
            attachments: data.data.attachments || existingMsg.attachments,  // Use SSE attachments if present
            timestamp: data.data.timestamp || existingMsg.timestamp  // Use SSE timestamp if present
          }
        } else {
          // Add new outbound message from SSE (e.g., sent from another tab)
          console.log('[SSE] Adding new outbound message from another session:', data.data.id)
          store.messages[recipientId].push(data.data)
        }
      }
      break
    case 'message_status':
      store.updateMessageStatus(data.data.message_id, data.data.status, data.data.error)
      break
  }
}

async function handleSelectConversation(senderId) {
  store.setActiveConversation(senderId)

  // Get account_id from the selected conversation
  const conversation = store.conversations.find(c => c.sender_id === senderId)
  const accountId = conversation?.account_id || accountsStore.selectedAccount?.account_id

  // Fetch messages if not already loaded
  if (!store.messages[senderId]) {
    await store.fetchMessages(senderId, accountId)
  }
}

async function handleSendMessage(formData, onProgress) {
  try {
    await store.sendMessage(formData, onProgress)
  } catch (err) {
    console.error('Failed to send message:', err)
    // Error is already stored in store.error
  }
}

async function refreshConversations() {
  // Pass selected account ID to fetch conversations for the active account
  const accountId = accountsStore.selectedAccount?.account_id || null
  await Promise.all([
    store.fetchCurrentAccount(),
    store.fetchConversations(accountId)
  ])
}

function getAccountInitial(username) {
  if (!username) return '?'
  // Remove @ symbol if present
  const cleanName = username.replace('@', '')
  return cleanName[0]?.toUpperCase() || '?'
}

onMounted(async () => {
  const sessionReady = await sessionStore.ensureSession()

  if (!sessionReady) {
    return
  }

  // Load accounts first, then fetch conversations for selected account
  await accountsStore.fetchAccounts()

  const accountId = accountsStore.selectedAccount?.account_id || null
  await Promise.all([
    store.fetchCurrentAccount(),
    store.fetchConversations(accountId)
  ])
})
</script>
