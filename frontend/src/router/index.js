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

  // Check if route requires authentication
  if (to.meta.requiresAuth) {
    // Try to restore session from localStorage
    sessionStore.restoreSession()

    // Check if user is authenticated
    if (!sessionStore.isAuthenticated) {
      // Redirect to login
      next('/login')
    } else {
      // User is authenticated, allow access
      next()
    }
  } else if (to.path === '/login') {
    // Check if user is already authenticated
    sessionStore.restoreSession()

    if (sessionStore.isAuthenticated) {
      // User is already authenticated and trying to access login page
      // Redirect to chat
      next('/')
    } else {
      // User not authenticated, allow access to login page
      next()
    }
  } else {
    // Route doesn't require authentication
    next()
  }
})

export default router
