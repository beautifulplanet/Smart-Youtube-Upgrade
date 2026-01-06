/**
 * YouTube Safety Inspector - Background Service Worker
 * Copyright (c) 2026 beautifulplanet
 * Licensed under MIT License
 * 
 * Data provided by YouTube Data API
 * https://developers.google.com/youtube
 */

const API_BASE_URL = 'http://localhost:8000';

// Cache for analysis results
const analysisCache = new Map();

// Rate limiting to prevent quota exhaustion
const rateLimiter = new Map();
const COOLDOWN_MS = 30000; // 30 seconds between same video analyses

function canAnalyze(videoId) {
  const lastCall = rateLimiter.get(videoId);
  const now = Date.now();
  
  if (lastCall && (now - lastCall) < COOLDOWN_MS) {
    console.log(`🛡️ Rate limit: Video ${videoId} analyzed ${Math.floor((now - lastCall) / 1000)}s ago, waiting...`);
    return false;
  }
  
  rateLimiter.set(videoId, now);
  return true;
}

// Listen for messages from content scripts or popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'ANALYZE_VIDEO') {
    analyzeVideo(message.videoId)
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
});

// Analyze a video
async function analyzeVideo(videoId) {
  console.log('🛡️ [BG] analyzeVideo called for:', videoId);
  
  // Check rate limit first
  if (!canAnalyze(videoId)) {
    // Return cached result if available
    if (analysisCache.has(videoId)) {
      console.log('🛡️ [BG] Returning cached result (rate limited)');
      return analysisCache.get(videoId);
    }
    throw new Error('Rate limited - please wait 30s before re-analyzing');
  }
  
  // Check cache first
  if (analysisCache.has(videoId)) {
    console.log('🛡️ [BG] Returning from cache');
    return analysisCache.get(videoId);
  }
  
  console.log('🛡️ [BG] Making API request to:', API_BASE_URL + '/analyze');
  
  const response = await fetch(`${API_BASE_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_id: videoId })
  });
  
  console.log('🛡️ [BG] API response status:', response.status);
  
  if (!response.ok) {
    console.error('🛡️ [BG] API request failed:', response.status, response.statusText);
    throw new Error('Analysis failed');
  }
  
  const results = await response.json();
  console.log('🛡️ [BG] API returned results, warnings:', results.warnings?.length || 0);
  analysisCache.set(videoId, results);
  
  // Update badge based on safety score
  updateBadge(results.safety_score);
  
  return results;
}

// Update extension badge
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

// Check if API is online
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
