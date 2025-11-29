/**
 * Helper for proxying Instagram CDN images through our backend
 * to bypass CORS and referrer restrictions
 */

/**
 * Convert Instagram CDN URL to proxied URL through our backend
 * @param {string|null|undefined} url - Instagram CDN image URL
 * @returns {string|null} Proxied URL or null if no URL provided
 */
export function getProxiedImageUrl(url) {
  if (!url) return null

  // Only proxy Instagram CDN URLs
  if (!url.startsWith('https://scontent.cdninstagram.com/')) {
    return url // Return as-is if not Instagram CDN
  }

  // Proxy through our backend
  return `/api/v1/ui/proxy-image?url=${encodeURIComponent(url)}`
}
