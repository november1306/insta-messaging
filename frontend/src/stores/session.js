import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

export const useSessionStore = defineStore('session', () => {
  // State
  const token = ref(null)
  const accountId = ref(null)
  const expiresAt = ref(null)
  const loading = ref(false)
  const error = ref(null)

  // Computed
  const isAuthenticated = computed(() => {
    if (!token.value || !expiresAt.value) {
      return false
    }
    // Check if token is expired
    return new Date() < new Date(expiresAt.value)
  })

  // Actions
  async function createSession() {
    loading.value = true
    error.value = null

    try {
      // Call session endpoint (protected by nginx basic auth)
      const response = await apiClient.post('/ui/session')

      if (response.data.error || !response.data.token) {
        throw new Error(response.data.error || 'Failed to create session')
      }

      // Store session data
      token.value = response.data.token
      accountId.value = response.data.account_id

      // Calculate expiration time
      const expiresInSeconds = response.data.expires_in
      const expirationDate = new Date()
      expirationDate.setSeconds(expirationDate.getSeconds() + expiresInSeconds)
      expiresAt.value = expirationDate.toISOString()

      // Persist to localStorage
      localStorage.setItem('session_token', token.value)
      localStorage.setItem('session_account_id', accountId.value)
      localStorage.setItem('session_expires_at', expiresAt.value)

      // Configure API client to use session token
      apiClient.defaults.headers.Authorization = `Bearer ${token.value}`

      console.log('Session created successfully for account:', accountId.value)

      return response.data
    } catch (err) {
      error.value = err.message || 'Failed to create session'
      console.error('Failed to create session:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  function restoreSession() {
    // Restore session from localStorage
    const storedToken = localStorage.getItem('session_token')
    const storedAccountId = localStorage.getItem('session_account_id')
    const storedExpiresAt = localStorage.getItem('session_expires_at')

    if (storedToken && storedAccountId && storedExpiresAt) {
      // Check if token is expired
      const expirationDate = new Date(storedExpiresAt)
      if (new Date() < expirationDate) {
        token.value = storedToken
        accountId.value = storedAccountId
        expiresAt.value = storedExpiresAt

        // Configure API client to use restored token
        apiClient.defaults.headers.Authorization = `Bearer ${storedToken}`

        console.log('Session restored from localStorage for account:', accountId.value)
        return true
      } else {
        // Token expired, clear localStorage
        console.log('Stored session expired, clearing...')
        clearSession()
      }
    }

    return false
  }

  function clearSession() {
    // Clear state
    token.value = null
    accountId.value = null
    expiresAt.value = null
    error.value = null

    // Clear localStorage
    localStorage.removeItem('session_token')
    localStorage.removeItem('session_account_id')
    localStorage.removeItem('session_expires_at')

    // Remove Authorization header from API client
    delete apiClient.defaults.headers.Authorization

    console.log('Session cleared')
  }

  async function ensureSession() {
    // Check if we have a valid session, create one if not
    if (isAuthenticated.value) {
      return true
    }

    // Try to restore from localStorage first
    if (restoreSession()) {
      return true
    }

    // Create new session
    try {
      await createSession()
      return true
    } catch (err) {
      console.error('Failed to ensure session:', err)
      return false
    }
  }

  return {
    // State
    token,
    accountId,
    expiresAt,
    loading,
    error,
    // Computed
    isAuthenticated,
    // Actions
    createSession,
    restoreSession,
    clearSession,
    ensureSession
  }
})
