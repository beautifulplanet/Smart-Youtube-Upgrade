/**
 * YouTube Safety Inspector - Background Service Worker
 * Copyright (c) 2026 beautifulplanet
 * Licensed under MIT License
 * 
 * Data provided by YouTube Data API
 * https://developers.google.com/youtube
 */

// Configuration - API URL configurable for production deployment
const DEFAULT_API_URL = 'http://localhost:8000';
let API_BASE_URL = DEFAULT_API_URL;

// Load API URL from storage on startup
chrome.storage.sync.get(['apiBaseUrl'], (result) => {
  if (result.apiBaseUrl) {
    API_BASE_URL = result.apiBaseUrl;
  }
});

// Cache for analysis results
const analysisCache = new Map();

// Rate limiting to prevent quota exhaustion
const rateLimiter = new Map();
const COOLDOWN_MS = 30000; // 30 seconds between same video analyses
const DAILY_LIMIT = 100; // Max 100 unique videos per day per user
let dailyRequestCount = 0;
let dailyResetDate = new Date().toDateString();

// Load persisted daily count from chrome.storage.local on startup
chrome.storage.local.get(['rateLimitCount', 'rateLimitDate'], (result) => {
  const today = new Date().toDateString();
  if (result.rateLimitDate === today) {
    dailyRequestCount = result.rateLimitCount || 0;
    dailyResetDate = today;
  }
});

/** Persist daily rate limit count to chrome.storage.local */
function persistDailyCount() {
  chrome.storage.local.set({
    rateLimitCount: dailyRequestCount,
    rateLimitDate: dailyResetDate
  });
}

/**
 * Check if a video can be analyzed (rate limiting).
 * Enforces per-video cooldown and daily request limit.
 * @param {string} videoId - YouTube video ID
 * @returns {boolean} Whether analysis is allowed
 */
function canAnalyze(videoId) {
  // Reset daily counter at midnight
  const today = new Date().toDateString();
  if (dailyResetDate !== today) {
    dailyRequestCount = 0;
    dailyResetDate = today;
    rateLimiter.clear();
    persistDailyCount();
  }

  // Check daily limit
  if (dailyRequestCount >= DAILY_LIMIT) {
    return false;
  }

  const lastCall = rateLimiter.get(videoId);
  const now = Date.now();

  if (lastCall && (now - lastCall) < COOLDOWN_MS) {
    return false;
  }

  rateLimiter.set(videoId, now);
  dailyRequestCount++;
  persistDailyCount();
  return true;
}

// Listen for messages from content scripts or popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'ANALYZE_VIDEO') {
    analyzeVideo(message.videoId, message.title, message.description, message.channel)
      .then(results => sendResponse({ success: true, data: results }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true; // Keep channel open for async response
  }

  if (message.type === 'GET_CACHED_ANALYSIS') {
    const cached = analysisCache.get(message.videoId);
    sendResponse({ success: !!cached, data: cached });
    return false;
  }

  if (message.type === 'CHECK_API_STATUS') {
    checkApiStatus()
      .then(status => sendResponse({ success: true, online: status }))
      .catch(() => sendResponse({ success: false, online: false }));
    return true;
  }

  // Generic API fetch handler - restricted to known endpoints only
  if (message.action === 'fetchAPI') {
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

/**
 * Make an API request to the backend.
 * @param {string} url - Full API URL
 * @param {string} [method='GET'] - HTTP method
 * @param {Object|null} [body=null] - Request body (JSON-serialized)
 * @returns {Promise<Object>} Parsed JSON response
 */
async function fetchFromAPI(url, method = 'GET', body = null) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' }
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
async function analyzeVideo(videoId, title = null, description = null, channel = null) {
  // Check rate limit first
  if (!canAnalyze(videoId)) {
    // Return cached result if available
    if (analysisCache.has(videoId)) {
      return analysisCache.get(videoId);
    }
    throw new Error('Rate limited - please wait 30s before re-analyzing');
  }

  // Check cache first
  if (analysisCache.has(videoId)) {
    return analysisCache.get(videoId);
  }

  // Include scraped metadata for AI detection (works without YouTube API key)
  const requestBody = {
    video_id: videoId,
    title: title,
    description: description,
    channel: channel
  };

  const response = await fetch(`${API_BASE_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody)
  });

  if (!response.ok) {
    console.error('🛡️ API request failed:', response.status, response.statusText);
    throw new Error('Analysis failed');
  }

  const results = await response.json();
  analysisCache.set(videoId, results);

  // Update badge based on safety score
  updateBadge(results.safety_score);

  return results;
}

/**
 * Update the extension toolbar badge based on safety score.
 * @param {number} score - Safety score (0-100)
 */
function updateBadge(score) {
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

  chrome.action.setBadgeBackgroundColor({ color });
  chrome.action.setBadgeText({ text });
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

// Clear badge when navigating away from YouTube
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.url && !changeInfo.url.includes('youtube.com/watch')) {
    chrome.action.setBadgeText({ text: '', tabId });
  }
});

// Clean up old cache entries periodically (keep last 50)
setInterval(() => {
  if (analysisCache.size > 50) {
    const keysToDelete = Array.from(analysisCache.keys()).slice(0, analysisCache.size - 50);
    keysToDelete.forEach(key => analysisCache.delete(key));
  }
}, 60000);
