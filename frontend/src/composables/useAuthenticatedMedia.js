/**
 * Composable for loading media files with authentication
 *
 * HTML <img> and <video> tags cannot send Authorization headers,
 * so we fetch media with credentials and convert to blob URLs.
 */
import { ref, onUnmounted } from 'vue'

// Cache blob URLs to avoid refetching
const blobUrlCache = new Map()

export function useAuthenticatedMedia() {
  const blobUrls = ref(new Set())

  /**
   * Fetch media file with authentication and return blob URL
   * @param {string} mediaPath - Relative path like "media/account/sender/file.jpg"
   * @returns {Promise<string>} - Blob URL for the media
   */
  async function fetchAuthenticatedMedia(mediaPath) {
    // Check cache first
    if (blobUrlCache.has(mediaPath)) {
      return blobUrlCache.get(mediaPath)
    }

    try {
      // Get JWT token from localStorage
      const token = localStorage.getItem('session_token')
      if (!token) {
        console.error('No session token found for authenticated media request')
        return null
      }

      // Fetch media with Authorization header
      // Use relative URL to work in both development and production
      const baseUrl = import.meta.env.DEV ? 'http://localhost:8000' : ''
      const response = await fetch(`${baseUrl}/${mediaPath}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (!response.ok) {
        console.error(`Failed to fetch media: ${response.status} ${response.statusText}`)
        return null
      }

      // Convert to blob
      const blob = await response.blob()
      const blobUrl = URL.createObjectURL(blob)

      // Cache the blob URL
      blobUrlCache.set(mediaPath, blobUrl)
      blobUrls.value.add(blobUrl)

      return blobUrl
    } catch (error) {
      console.error('Error fetching authenticated media:', error)
      return null
    }
  }

  /**
   * Download file attachment with authentication
   * @param {string} mediaPath - Relative path like "media/account/sender/file.pdf"
   * @param {string} filename - Desired filename for download
   */
  async function downloadAuthenticatedFile(mediaPath, filename) {
    try {
      // Get JWT token from localStorage
      const token = localStorage.getItem('session_token')
      if (!token) {
        console.error('No session token found for authenticated download')
        return
      }

      // Fetch file with Authorization header
      // Use relative URL to work in both development and production
      const baseUrl = import.meta.env.DEV ? 'http://localhost:8000' : ''
      const response = await fetch(`${baseUrl}/${mediaPath}?download=true`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (!response.ok) {
        console.error(`Failed to download file: ${response.status} ${response.statusText}`)
        return
      }

      // Convert to blob
      const blob = await response.blob()

      // Create temporary download link and trigger download
      const blobUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = blobUrl
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      // Cleanup blob URL after a short delay
      setTimeout(() => URL.revokeObjectURL(blobUrl), 100)
    } catch (error) {
      console.error('Error downloading authenticated file:', error)
    }
  }

  /**
   * Cleanup blob URLs when component unmounts
   */
  onUnmounted(() => {
    blobUrls.value.forEach(url => {
      URL.revokeObjectURL(url)
      // Remove from cache
      for (const [key, value] of blobUrlCache.entries()) {
        if (value === url) {
          blobUrlCache.delete(key)
        }
      }
    })
    blobUrls.value.clear()
  })

  return {
    fetchAuthenticatedMedia,
    downloadAuthenticatedFile
  }
}
