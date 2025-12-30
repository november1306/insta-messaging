import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

export const useMessagesStore = defineStore('messages', () => {
  // State
  const conversations = ref([])
  const messages = ref({}) // Keyed by sender_id
  const activeConversationId = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const currentAccount = ref(null) // Current user's account info

  // Computed
  const activeConversation = computed(() => {
    return conversations.value.find(c => c.sender_id === activeConversationId.value)
  })

  const activeMessages = computed(() => {
    return messages.value[activeConversationId.value] || []
  })

  // Actions
  async function fetchCurrentAccount() {
    try {
      const response = await apiClient.get('/ui/account/me')
      currentAccount.value = response.data
    } catch (err) {
      console.error('Failed to fetch current account:', err)
      currentAccount.value = {
        account_id: null,
        username: 'Error loading account',
        instagram_handle: null
      }
    }
  }

  async function fetchConversations(accountId = null) {
    loading.value = true
    error.value = null
    try {
      const params = accountId ? { account_id: accountId } : {}
      const response = await apiClient.get('/ui/conversations', { params })
      conversations.value = response.data.conversations
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch conversations:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchMessages(senderId, accountId = null) {
    loading.value = true
    error.value = null
    try {
      // Build URL with optional account_id parameter
      const url = accountId
        ? `/ui/messages/${senderId}?account_id=${accountId}`
        : `/ui/messages/${senderId}`

      const response = await apiClient.get(url)
      messages.value[senderId] = response.data.messages
      activeConversationId.value = senderId
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch messages:', err)
    } finally {
      loading.value = false
    }
  }

  async function sendMessage(formData, onProgress) {
    error.value = null

    // Extract values for optimistic update BEFORE making the request
    const recipientId = formData.get('recipient_id')
    const messageText = formData.get('message') || ''
    const hasFile = formData.get('file') !== null

    // Generate temporary ID for optimistic update
    const tempId = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    // Add optimistic update IMMEDIATELY (before API call)
    const sentMessage = {
      id: tempId,
      tempId: tempId,  // Keep temp ID for matching even after ID update
      text: messageText,
      direction: 'outbound',
      timestamp: new Date().toISOString(),
      status: 'pending',
      attachments: [],
      recipientId: recipientId  // Store recipient ID for SSE matching
    }

    if (!messages.value[recipientId]) {
      messages.value[recipientId] = []
    }
    messages.value[recipientId].push(sentMessage)

    console.log('[Optimistic] Adding message BEFORE API call:', {
      id: tempId,
      text: messageText,
      recipient_id: recipientId,
      status: 'pending'
    })

    try {
      // Send FormData directly with progress tracking
      const response = await apiClient.post('/messages/send', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          if (onProgress && progressEvent.total) {
            const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100)
            onProgress(progress)
          }
        }
      })

      console.log('[Optimistic] API response received, updating temp message:', {
        tempId,
        trackingId: response.data.message_id
      })

      // Update the optimistic message with tracking ID from response
      const msgIndex = messages.value[recipientId].findIndex(m => m.tempId === tempId || m.id === tempId)
      if (msgIndex >= 0 && messages.value[recipientId][msgIndex]) {
        // Defensive check: Verify message still exists at index (prevents race condition)
        const msg = messages.value[recipientId][msgIndex]

        // Double-check this is still the correct message
        if (msg.tempId === tempId || msg.id === tempId) {
          msg.id = response.data.message_id  // Replace temp ID with tracking ID
          msg.trackingId = response.data.message_id  // Also store as trackingId for SSE matching
          msg.status = response.data.status || 'sent'

          // Add attachment if present in response
          if (hasFile && response.data.attachment_local_path) {
            msg.attachments = [{
              id: `${response.data.message_id}_0`,
              media_type: response.data.attachment_type || 'image',
              media_url: response.data.attachment_url,  // Public URL
              media_url_local: response.data.attachment_local_path,  // Local path for authenticated fetch
              attachment_index: 0
            }]
          }
        }
      }

      // Note: SSE will update the status to 'sent' or 'failed' in real-time
      return response.data
    } catch (err) {
      // Remove optimistic message on error
      const msgIndex = messages.value[recipientId].findIndex(m => m.id === tempId)
      if (msgIndex >= 0) {
        messages.value[recipientId].splice(msgIndex, 1)
      }

      error.value = err.message
      console.error('Failed to send message:', err)
      throw err
    }
  }

  function addIncomingMessage(message) {
    const senderId = message.sender_id

    // Update or create conversation
    const convIndex = conversations.value.findIndex(c => c.sender_id === senderId)
    if (convIndex >= 0) {
      conversations.value[convIndex].last_message = message.text
      conversations.value[convIndex].last_message_time = message.timestamp
      conversations.value[convIndex].unread_count = (conversations.value[convIndex].unread_count || 0) + 1
    } else {
      conversations.value.unshift({
        sender_id: senderId,
        sender_name: message.sender_name || senderId,
        last_message: message.text,
        last_message_time: message.timestamp,
        unread_count: 1,
        messaging_channel_id: message.messaging_channel_id,  // Messaging channel that received the message
        account_id: message.account_id  // Database account ID for sending messages
      })
    }

    // Add message to messages list
    if (!messages.value[senderId]) {
      messages.value[senderId] = []
    }
    messages.value[senderId].push(message)
  }

  function updateMessageStatus(messageId, status, errorMessage = null) {
    // Find and update message status across all conversations
    for (const senderId in messages.value) {
      const msgIndex = messages.value[senderId].findIndex(m => m.id === messageId)
      if (msgIndex >= 0) {
        messages.value[senderId][msgIndex].status = status
        if (errorMessage) {
          messages.value[senderId][msgIndex].error = errorMessage
        }
        break
      }
    }
  }

  function setActiveConversation(senderId) {
    activeConversationId.value = senderId

    // Mark as read
    const conv = conversations.value.find(c => c.sender_id === senderId)
    if (conv) {
      conv.unread_count = 0
    }
  }

  return {
    // State
    conversations,
    messages,
    activeConversationId,
    loading,
    error,
    currentAccount,
    // Computed
    activeConversation,
    activeMessages,
    // Actions
    fetchCurrentAccount,
    fetchConversations,
    fetchMessages,
    sendMessage,
    addIncomingMessage,
    updateMessageStatus,
    setActiveConversation
  }
})
