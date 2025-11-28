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
  async function login(username, password) {
    loading.value = true
    error.value = null

    try {
      // Encode credentials as Basic Auth
      const credentials = btoa(`${username}:${password}`)

      // Call session endpoint with Basic Auth header
      const response = await apiClient.post('/ui/session', null, {
        headers: {
          'Authorization': `Basic ${credentials}`
        }
      })

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

      console.log('[Session] Session created successfully for account:', accountId.value)
      console.log('[Session] Token stored in localStorage')
      console.log('[Session] isAuthenticated:', isAuthenticated.value)

      return response.data
    } catch (err) {
      // Extract error message from response
      const errorMessage = err.response?.data?.detail || err.message || 'Invalid username or password'
      error.value = errorMessage
      console.error('Failed to create session:', err)
      throw new Error(errorMessage)
    } finally {
      loading.value = false
    }
  }

  async function createSession() {
    // Deprecated: Use login() instead
    // This function is kept for backwards compatibility during migration
    throw new Error('Please use login() with username and password')
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

    console.log('[Session] Session cleared')
  }

  function logout() {
    console.log('[Session] Logging out...')
    clearSession()
    // Router will handle redirect to login via navigation guard
    return true
  }

  async function ensureSession() {
    // Check if we have a valid session
    if (isAuthenticated.value) {
      return true
    }

    // Try to restore from localStorage
    if (restoreSession()) {
      return true
    }

    // No valid session - user needs to login
    console.log('No valid session found - user needs to login')
    return false
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
    login,
    logout,
    createSession, // deprecated
    restoreSession,
    clearSession,
    ensureSession
  }
})
