/**
 * Extracted pure functions from extension/content/utils.js
 * These mirror the originals exactly but are importable for testing.
 */

/**
 * Get video ID from a URL string
 * @param {string} url 
 * @returns {string|null}
 */
export function getVideoId(url) {
  // Regular video: youtube.com/watch?v=VIDEO_ID (exactly 11 valid chars)
  const watchMatch = url.match(/[?&]v=([a-zA-Z0-9_-]{11})(?:&|$)/);
  if (watchMatch) return watchMatch[1];

  // Shorts: youtube.com/shorts/VIDEO_ID (exactly 11 valid chars)
  const shortsMatch = url.match(/\/shorts\/([a-zA-Z0-9_-]{11})(?:[/?]|$)/);
  if (shortsMatch) return shortsMatch[1];

  return null;
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text
 * @returns {string}
 */
export function escapeHtml(text) {
  if (!text) return '';
  return String(text).replace(/[&<>"']/g, m => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[m]);
}

/**
 * Validate that an API URL matches the allowlist.
 * Mirrors background.js / popup.js isAllowedApiUrl.
 */
const ALLOWED_API_PATTERNS = [
  /^https?:\/\/localhost(:\d{1,5})?$/,
  /^https?:\/\/127\.0\.0\.1(:\d{1,5})?$/,
  /^https:\/\/[a-z0-9-]+\.beautifulplanet\.dev$/,
];

export function isAllowedApiUrl(url) {
  return ALLOWED_API_PATTERNS.some(pattern => pattern.test(url));
}

/**
 * Default settings from popup.js
 */
export const DEFAULT_SETTINGS = {
  enableAIDetection: true,
  autoAnalyze: true,
  enableRegularVideos: true,
  enableShorts: true,
  enableAlternatives: true,
  enableAITutorials: true,
  enableAIEntertainment: true,
  bannerStyle: 'modal',
  autoDismiss: 0,
  enableReminders: true,
  enableEndAlert: true,
  enableSound: false,
  enableVisualEffects: true,
  aiSensitivity: 'medium',
  safetySensitivity: 'medium',
  enableCache: true,
  trustedChannels: ['National Geographic', 'BBC Earth', 'The Dodo', 'Discovery', 'Smithsonian Channel', 'PBS Nature'],
};

/**
 * Allowed endpoint patterns from background.js
 */
export const ALLOWED_ENDPOINTS = [
  '/analyze', '/ai-tutorials', '/ai-entertainment',
  '/real-alternatives', '/health', '/signatures', '/categories'
];

/**
 * Check if an endpoint is in the allowed list
 * @param {string} endpoint
 * @returns {boolean}
 */
export function isAllowedEndpoint(endpoint) {
  return ALLOWED_ENDPOINTS.some(allowed => endpoint === allowed || endpoint.startsWith(allowed + '?'));
}
