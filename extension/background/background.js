/**
 * YouTube Safety Inspector - Background Service Worker
 * Copyright (c) 2026 beautifulplanet
 * Licensed under MIT License
 * 
 * Data provided by YouTube Data API
 * https://developers.google.com/youtube
 */

// Note: For Firefox MV3 support, add browser-polyfill.min.js to lib/ and
// uncomment the following line. Chrome/Edge use native chrome.* APIs.
// if (typeof importScripts !== 'undefined') {
//   try { importScripts('lib/browser-polyfill.min.js'); } catch (_e) { }
// }

// Global error handlers — keeps the service worker alive on unexpected errors
self.addEventListener('unhandledrejection', (event) => {
  console.error('🛡️ Unhandled rejection in service worker:', event.reason);
});
self.addEventListener('error', (event) => {
  console.error('🛡️ Uncaught error in service worker:', event.error);
});

// Configuration - API URL configurable for production deployment
// SYNC: also declared in popup/popup.js — keep both in sync
const DEFAULT_API_URL = 'http://localhost:8000';
const ALLOWED_API_PATTERNS = [
  /^https?:\/\/localhost(:\d{1,5})?$/,
  /^https?:\/\/127\.0\.0\.1(:\d{1,5})?$/,
  /^https:\/\/[a-z0-9-]+\.beautifulplanet\.dev$/,
];
let API_BASE_URL = DEFAULT_API_URL;

/** Validate that an API URL matches the allowlist. */
function isAllowedApiUrl(url) {
  return ALLOWED_API_PATTERNS.some(pattern => pattern.test(url));
}

// Load API URL from storage on startup
chrome.storage.sync.get(['apiBaseUrl'], (result) => {
  if (result.apiBaseUrl && isAllowedApiUrl(result.apiBaseUrl)) {
    API_BASE_URL = result.apiBaseUrl;
  } else if (result.apiBaseUrl) {
    console.warn('🛡️ Rejected untrusted API URL from storage:', result.apiBaseUrl);
  }
});

/**
 * W2.1: Storage Wrapper
 * Helper to handle async storage calls cleanly.
 * Falls back to local storage if session is unavailable (e.g. Firefox pending MV3 support).
 */
const storage = {
  // session: ephemeral, clears on browser close. Good for cache & rate limits.
  // local: persistent. Good for daily counts.

  async get(key, area = 'session') {
    try {
      // Firefox MV3 doesn't fully support storage.session in content scripts yet,
      // but does in background. Safety check just in case.
      const useArea = (area === 'session' && !chrome.storage.session) ? 'local' : area;
      const result = await chrome.storage[useArea].get(key);
      return result[key];
    } catch (e) {
      console.warn(`Storage get error (${area}):`, e);
      return null;
    }
  },

  async set(key, value, area = 'session') {
    try {
      const useArea = (area === 'session' && !chrome.storage.session) ? 'local' : area;
      await chrome.storage[useArea].set({ [key]: value });
    } catch (e) {
      console.warn(`Storage set error (${area}):`, e);
    }
  },

  async remove(key, area = 'session') {
    try {
      const useArea = (area === 'session' && !chrome.storage.session) ? 'local' : area;
      await chrome.storage[useArea].remove(key);
    } catch (e) {
      console.warn(`Storage remove error (${area}):`, e);
    }
  }
};

// Rate limiting to prevent quota exhaustion
const COOLDOWN_MS = 30000; // 30 seconds between same video analyses
const DAILY_LIMIT = 100; // Max 100 unique videos per day per user

/**
 * W2.3: Async Rate Limiter
 * Check if a video can be analyzed.
 * Enforces per-video cooldown (session storage) and daily request limit (local storage).
 * @param {string} videoId - YouTube video ID
 * @returns {Promise<boolean>} Whether analysis is allowed
 */
// Mutex to prevent TOCTOU race on concurrent canAnalyze calls
let _rateLimitLock = Promise.resolve();

async function canAnalyze(videoId) {
  // Serialize access to prevent two concurrent calls both reading the same count
  const release = _rateLimitLock;
  let _resolve;
  _rateLimitLock = new Promise(r => { _resolve = r; });
  await release;

  try {
    const today = new Date().toDateString();

    // 1. Get daily limit state (persistent)
    const localState = await storage.get('rateLimitState', 'local') || { count: 0, date: today };

    // Reset if new day
    if (localState.date !== today) {
      localState.count = 0;
      localState.date = today;
    }

    // Check daily limit
    if (localState.count >= DAILY_LIMIT) {
      console.warn(`Daily limit reached: ${localState.count}/${DAILY_LIMIT}`);
      return false;
    }

    // 2. Check cooldown (session ephemeral)
    const lastCall = await storage.get(`cooldown_${videoId}`, 'session');
    const now = Date.now();

    if (lastCall && (now - lastCall) < COOLDOWN_MS) {
      return false;
    }

    // 3. Atomically update both counters before releasing the lock
    await storage.set(`cooldown_${videoId}`, now, 'session');
    localState.count++;
    await storage.set('rateLimitState', localState, 'local');

    return true;
  } finally {
    _resolve();
  }
}

// Listen for messages from content scripts or popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'ANALYZE_VIDEO') {
    const tabId = sender?.tab?.id;
    // Return true to keep channel open for async response
    analyzeVideo(message.videoId, message.title, message.description, message.channel, message.force)
      .then(results => {
        updateBadge(results.safety_score, tabId);
        sendResponse({ success: true, data: results });
      })
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }

  if (message.type === 'GET_CACHED_ANALYSIS') {
    // W2.2: Async cache retrieval
    storage.get(`cache_${message.videoId}`, 'session').then(cached => {
      sendResponse({ success: !!cached, data: cached });
    });
    return true; // Keep channel open
  }

  if (message.type === 'CHECK_API_STATUS') {
    checkApiStatus()
      .then(status => sendResponse({ success: true, online: status }))
      .catch(() => sendResponse({ success: false, online: false }));
    return true;
  }

  // Generic API fetch handler - restricted to known endpoints only
  if (message.type === 'FETCH_API') {
    // Security: Only allow known API endpoints, never arbitrary URLs
    const ALLOWED_ENDPOINTS = ['/analyze', '/ai-tutorials', '/ai-entertainment', '/real-alternatives', '/health', '/signatures', '/categories'];
    const endpoint = message.endpoint;

    if (!endpoint || !ALLOWED_ENDPOINTS.includes(endpoint.split('?')[0])) {
      sendResponse({ success: false, error: 'Invalid API endpoint' });
      return false;
    }

    const url = `${API_BASE_URL}${endpoint}`;

    fetchFromAPI(url, message.method, message.body)
      .then(data => sendResponse({ success: true, data }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }
});

// Load API key from storage (optional, for authenticated backends)
let _apiSecretKey = '';
chrome.storage.sync.get(['apiSecretKey'], (result) => {
  if (result.apiSecretKey) _apiSecretKey = result.apiSecretKey;
});

/**
 * Make an API request to the backend.
 * @param {string} url - Full API URL
 * @param {string} [method='GET'] - HTTP method
 * @param {Object|null} [body=null] - Request body (JSON-serialized)
 * @returns {Promise<Object>} Parsed JSON response
 */
async function fetchFromAPI(url, method = 'GET', body = null) {
  const headers = { 'Content-Type': 'application/json' };
  // Include API key if configured (for authenticated backends)
  if (_apiSecretKey) headers['X-API-Key'] = _apiSecretKey;

  const options = {
    method,
    headers
  };

  if (body && method !== 'GET') {
    options.body = JSON.stringify(body);
  }

  const response = await fetch(url, options);

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return await response.json();
}

/**
 * Analyze a video via the backend API. Checks rate limits and cache first.
 * @param {string} videoId - YouTube video ID
 * @param {string|null} [title] - Scraped video title
 * @param {string|null} [description] - Scraped video description
 * @param {string|null} [channel] - Scraped channel name
 * @returns {Promise<Object>} Analysis results
 */
async function analyzeVideo(videoId, title = null, description = null, channel = null, force = false) {
  console.log('🛡️ analyzeVideo called:', videoId, '| API:', API_BASE_URL, '| force:', force);

  // W2.2: Check cache from storage first (skip if force re-analyze)
  if (!force) {
    const cached = await storage.get(`cache_${videoId}`, 'session');
    if (cached) {
      console.log('🛡️ Returning cached result for:', videoId);
      return cached;
    }
  } else {
    // Clear old cache for this video
    await storage.remove(`cache_${videoId}`, 'session');
    console.log('🛡️ Force re-analyze: cleared cache for:', videoId);
  }

  // W2.4: Check rate limit (Async)
  const allowed = await canAnalyze(videoId);
  if (!allowed) {
    throw new Error('Rate limited - please wait 30s before re-analyzing');
  }

  // Include scraped metadata for AI detection (works without YouTube API key)
  const requestBody = {
    video_id: videoId,
    title: title,
    description: description,
    channel: channel
  };

  console.log('🛡️ Fetching:', `${API_BASE_URL}/analyze`, requestBody);
  // Use fetchFromAPI so X-API-Key header is included when configured
  const results = await fetchFromAPI(`${API_BASE_URL}/analyze`, 'POST', requestBody);
  console.log('🛡️ Analysis result: score=' + results.safety_score + ', ai=' + results.ai_generated + ', warnings=' + (results.warnings || []).length);

  // W2.2: Write to storage cache (expires on browser close)
  // Prefixed with cache_ to avoid collisions
  await storage.set(`cache_${videoId}`, results, 'session');

  return results;
}

/**
 * Update the extension toolbar badge based on safety score.
 * @param {number} score - Safety score (0-100)
 */
function updateBadge(score, tabId) {
  let color, text;

  if (score < 40) {
    color = '#ff4444';
    text = '!';
  } else if (score < 70) {
    color = '#ffaa00';
    text = '?';
  } else {
    color = '#00ff88';
    text = '✓';
  }

  const tabOpts = tabId ? { tabId } : {};
  chrome.action.setBadgeBackgroundColor({ color, ...tabOpts });
  chrome.action.setBadgeText({ text, ...tabOpts });
}

/**
 * Check if the backend API is reachable.
 * @returns {Promise<boolean>} True if API responds within 3 seconds
 */
async function checkApiStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(3000)
    });
    return response.ok;
  } catch {
    return false;
  }
}

// Clear badge when navigating away from YouTube videos
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.url && !changeInfo.url.includes('youtube.com/watch') && !changeInfo.url.includes('youtube.com/shorts/')) {
    chrome.action.setBadgeText({ text: '', tabId });
  }
});


