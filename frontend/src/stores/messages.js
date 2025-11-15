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

  // Computed
  const activeConversation = computed(() => {
    return conversations.value.find(c => c.sender_id === activeConversationId.value)
  })

  const activeMessages = computed(() => {
    return messages.value[activeConversationId.value] || []
  })

  // Actions
  async function fetchConversations() {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.get('/ui/conversations')
      conversations.value = response.data.conversations
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch conversations:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchMessages(senderId) {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.get(`/ui/messages/${senderId}`)
      messages.value[senderId] = response.data.messages
      activeConversationId.value = senderId
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch messages:', err)
    } finally {
      loading.value = false
    }
  }

  async function sendMessage(recipientId, text, accountId) {
    error.value = null
    try {
      const response = await apiClient.post('/messages/send', {
        recipient_id: recipientId,
        text: text,
        account_id: accountId
      })

      // Add sent message to local state
      const sentMessage = {
        id: response.data.message_id,
        text: text,
        direction: 'outbound',
        timestamp: new Date().toISOString(),
        status: response.data.status
      }

      if (!messages.value[recipientId]) {
        messages.value[recipientId] = []
      }
      messages.value[recipientId].push(sentMessage)

      return response.data
    } catch (err) {
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
        instagram_account_id: message.instagram_account_id
      })
    }

    // Add message to messages list
    if (!messages.value[senderId]) {
      messages.value[senderId] = []
    }
    messages.value[senderId].push(message)
  }

  function updateMessageStatus(messageId, status) {
    // Find and update message status across all conversations
    for (const senderId in messages.value) {
      const msgIndex = messages.value[senderId].findIndex(m => m.id === messageId)
      if (msgIndex >= 0) {
        messages.value[senderId][msgIndex].status = status
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
    // Computed
    activeConversation,
    activeMessages,
    // Actions
    fetchConversations,
    fetchMessages,
    sendMessage,
    addIncomingMessage,
    updateMessageStatus,
    setActiveConversation
  }
})
