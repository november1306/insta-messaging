import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import LoginView from '../views/LoginView.vue'
import { useSessionStore } from '../stores/session'

const router = createRouter({
  history: createWebHistory('/chat/'),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { requiresAuth: false }
    },
    {
      path: '/',
      name: 'chat',
      component: ChatView,
      meta: { requiresAuth: true }
    }
  ]
})

// Navigation guard for authentication
router.beforeEach((to, from, next) => {
  const sessionStore = useSessionStore()

  console.log(`[Router] Navigating from ${from.path} to ${to.path}`)
  console.log(`[Router] Route requires auth: ${to.meta.requiresAuth}`)

  // Check if route requires authentication
  if (to.meta.requiresAuth) {
    // Try to restore session from localStorage
    sessionStore.restoreSession()

    console.log(`[Router] User authenticated: ${sessionStore.isAuthenticated}`)

    // Check if user is authenticated
    if (!sessionStore.isAuthenticated) {
      // Redirect to login
      console.log('[Router] User not authenticated, redirecting to login')
      next('/login')
    } else {
      // User is authenticated, allow access
      console.log('[Router] User authenticated, allowing access')
      next()
    }
  } else if (to.path === '/login') {
    // Check if user is already authenticated
    sessionStore.restoreSession()

    if (sessionStore.isAuthenticated) {
      // User is already authenticated and trying to access login page
      // Redirect to chat
      console.log('[Router] User already authenticated, redirecting to chat')
      next('/')
    } else {
      // User not authenticated, allow access to login page
      console.log('[Router] Allowing access to login page')
      next()
    }
  } else {
    // Route doesn't require authentication
    console.log('[Router] Route does not require auth, allowing access')
    next()
  }
})

export default router
