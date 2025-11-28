import axios from 'axios'

/**
 * API Client for frontend requests
 *
 * Authentication is managed by the session store:
 * 1. Session store calls POST /ui/session to get JWT token
 * 2. Session store sets apiClient.defaults.headers.Authorization
 * 3. All subsequent requests use the JWT token automatically
 *
 * Note: The /ui/session endpoint itself is protected by nginx basic auth
 */
const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json'
    // Authorization header is set dynamically by session store
  },
  timeout: 10000
})

// Request interceptor
apiClient.interceptors.request.use(
  config => {
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// Response interceptor
apiClient.interceptors.response.use(
  response => {
    return response
  },
  error => {
    if (error.response) {
      // Server responded with error status
      const status = error.response.status
      const errorData = error.response.data

      // Handle authentication errors
      if (status === 401) {
        console.warn('Authentication failed (401) - session may be expired:', errorData)
        // Session store should handle clearing expired sessions
        // Components can listen for 401 errors to trigger re-authentication
      }

      console.error('API Error:', status, errorData)
    } else if (error.request) {
      // No response received
      console.error('Network Error:', error.message)
    } else {
      // Error setting up request
      console.error('Request Error:', error.message)
    }
    return Promise.reject(error)
  }
)

export default apiClient
