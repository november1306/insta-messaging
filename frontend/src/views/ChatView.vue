<template>
  <div class="flex flex-col h-screen bg-white">
    <!-- Top: Account Tabs -->
    <AccountTabs
      ref="accountTabsRef"
      :sse-connected="sseConnected"
      :sse-error="sseError"
      @show-account-details="handleShowAccountDetails"
    />

    <!-- Main Content: 3-column layout (responsive) -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Left: Conversation List -->
      <!-- Mobile: Show full width when no conversation selected, hide when conversation selected -->
      <!-- Tablet (md): Show as sidebar (20rem width) -->
      <!-- Desktop (lg+): Show as sidebar (20rem width) -->
      <div
        :class="[
          'border-r border-instagram-border flex flex-col',
          'w-full md:w-80',
          store.activeConversationId ? 'hidden md:flex' : 'flex'
        ]"
      >
        <ConversationList
          :conversations="filteredConversations"
          :active-id="store.activeConversationId"
          :loading="store.loading"
          @select="handleSelectConversation"
          @refresh="refreshConversations"
        />
      </div>

      <!-- Center: Message Thread -->
      <!-- Mobile: Show full width when conversation selected -->
      <!-- Tablet/Desktop: Show as flex-1 (remaining space) -->
      <div
        :class="[
          'flex flex-col',
          store.activeConversationId ? 'flex-1' : 'hidden md:flex md:flex-1'
        ]"
      >
        <!-- Back button for mobile -->
        <div
          v-if="store.activeConversationId"
          class="md:hidden border-b border-instagram-border bg-white px-4 py-3 flex items-center gap-3"
        >
          <button
            @click="handleBackToConversations"
            class="p-2 hover:bg-gray-100 rounded-full transition-colors"
            title="Back to conversations"
          >
            <svg class="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div class="flex-1">
            <h2 class="font-semibold text-gray-900">{{ store.activeConversation?.sender_name }}</h2>
          </div>
        </div>

        <MessageThread
          v-if="store.activeConversationId"
          :conversation="store.activeConversation"
          :messages="store.activeMessages"
          :loading="store.loading"
          @send="handleSendMessage"
        />
        <div v-else class="flex-1 flex items-center justify-center text-gray-400">
          <div class="text-center px-4">
            <svg class="w-24 h-24 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <p class="text-xl">Select a conversation to start messaging</p>
          </div>
        </div>
      </div>

      <!-- Right: Account or Conversation Details -->
      <!-- Hidden on mobile and tablet, shown on large screens (lg+) -->
      <div class="hidden lg:flex lg:w-80 border-l border-instagram-border">
        <!-- Account Details -->
        <AccountDetailsPanel
          v-if="activeAccountDetails"
          :account="activeAccountDetails"
          @unlink="handleUnlink"
          @delete="handleDelete"
        />
        <!-- Conversation Details -->
        <ConversationDetails
          v-else-if="store.activeConversation"
          :conversation="store.activeConversation"
        />
        <!-- Placeholder -->
        <div v-else class="flex items-center justify-center h-full w-full text-gray-400">
          <div class="text-center px-6">
            <svg class="w-16 h-16 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p class="text-sm font-medium text-gray-600">Details</p>
            <p class="text-xs text-gray-500 mt-1">Select an account or conversation</p>
          </div>
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
import ConversationList from '../components/ConversationList.vue'
import MessageThread from '../components/MessageThread.vue'
import AccountTabs from '../components/AccountTabs.vue'
import ConversationDetails from '../components/ConversationDetails.vue'
import AccountDetailsPanel from '../components/AccountDetailsPanel.vue'

const router = useRouter()
const store = useMessagesStore()
const sessionStore = useSessionStore()
const accountsStore = useAccountsStore()

// Refs
const accountTabsRef = ref(null)
const activeAccountDetails = ref(null)

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

      // Auto-select the most recent conversation for the new account
      // filteredConversations is sorted by last_message_time (most recent first)
      if (filteredConversations.value.length > 0) {
        const mostRecent = filteredConversations.value[0]
        await handleSelectConversation(mostRecent.sender_id)
      } else {
        // No conversations for this account - clear selection
        store.setActiveConversation(null)
      }
    }
  }
)

// SSE connection for real-time updates
const { connected: sseConnected, error: sseError } = useSSE(
  '/api/v1/events',
  handleSSEMessage
)

async function handleSSEMessage(data) {
  switch (data.event) {
    case 'new_message':
      // Handle both inbound and outbound messages
      if (data.data.direction === 'inbound') {
        store.addIncomingMessage(data.data)

        // If this is potentially the first message after OAuth linking (no channel ID yet),
        // refresh accounts from server to get the updated messaging_channel_id.
        // Backend already handles channel binding via _bind_channel_id() in webhook handler.
        if (accountsStore.selectedAccount && !accountsStore.selectedAccount.messaging_channel_id) {
          accountsStore.fetchAccounts().catch(err => {
            console.error('[SSE] Failed to refresh accounts:', err)
          })
        }
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
          store.messages[recipientId].push(data.data)
        }
      }
      break
    case 'message_status':
      console.log('📊 Message status update:', data.data)

      // Extract error message if status is failed
      let errorMessage = null
      if (data.data.status === 'failed') {
        errorMessage = data.data.error_message || 'Message send failed'
      }

      // Update message status in store with error details
      store.updateMessageStatus(
        data.data.message_id,
        data.data.status,
        errorMessage
      )
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

function handleBackToConversations() {
  // Clear active conversation to show conversation list on mobile
  store.setActiveConversation(null)
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

// ============================================
// Account Details Handlers
// ============================================

function handleShowAccountDetails(account) {
  activeAccountDetails.value = account
}

function handleUnlink() {
  if (activeAccountDetails.value && accountTabsRef.value) {
    accountTabsRef.value.unlinkAccount(activeAccountDetails.value)
    // Close account details panel after unlinking
    activeAccountDetails.value = null
  }
}

function handleDelete() {
  if (activeAccountDetails.value && accountTabsRef.value) {
    accountTabsRef.value.showDeleteModal(activeAccountDetails.value)
    // Close account details panel when opening delete modal
    activeAccountDetails.value = null
  }
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
