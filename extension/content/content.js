/**
 * YouTube Safety Inspector - Content Script Entry Point
 * Copyright (c) 2026 beautifulplanet
 * Licensed under MIT License
 * 
 * This file coordinates:
 * 1. utils.js - Helper functions
 * 2. overlay.js - UI injection
 * 3. analysis.js - Core logic
 */

console.log('🛡️ Safety Inspector v2.1.0 loaded');

// --- Initialization ---

/** Initialize the content script: set up URL observers and check current page. */
function init() {
  try {
    // YouTube is a Single Page App (SPA), so we need to watch for URL changes
    observeUrlChanges();

    // Initial check if we landed directly on a video
    const videoId = getVideoId();
    if (videoId) {
      // Small delay to let YouTube UI hydrate
      setTimeout(() => {
        checkVideo(videoId);
      }, 1000);
    }
  } catch (err) {
    console.error('🛡️ Fatal error in init:', err);
  }
}

// --- Navigation Handling ---

let lastUrl = location.href;
let _urlChangeTimer = null;
const URL_CHANGE_DEBOUNCE_MS = 300;

/** Listen for YouTube SPA navigation events and browser back/forward. */
function observeUrlChanges() {
  try {
    // YouTube's official SPA navigation event (most reliable)
    window.addEventListener('yt-navigate-finish', () => {
      debouncedUrlChange(location.href);
    });

    // popstate covers browser back/forward
    window.addEventListener('popstate', () => {
      debouncedUrlChange(location.href);
    });
  } catch (err) {
    console.error('🛡️ Error setting up observers:', err);
  }
}

/**
 * Debounce URL change events to avoid duplicate analysis triggers.
 * @param {string} url - New page URL
 */
function debouncedUrlChange(url) {
  if (_urlChangeTimer) clearTimeout(_urlChangeTimer);
  _urlChangeTimer = setTimeout(() => {
    if (url !== lastUrl) {
      lastUrl = url;
      onUrlChange(url);
    }
  }, URL_CHANGE_DEBOUNCE_MS);
}

/**
 * Handle URL change: hide previous overlays and trigger analysis if on a video.
 * @param {string} url - New page URL
 */
function onUrlChange(url) {
  try {
    // Always hide overlays on navigation
    if (typeof hideAllOverlays === 'function') hideAllOverlays();

    // Check if it's a video
    const videoId = getVideoId();
    if (videoId) {
      // Give YouTube a moment to update the DOM
      setTimeout(() => {
        checkVideo(videoId);
      }, 1000);
    }
  } catch (err) {
    console.error('🛡️ Error in onUrlChange:', err);
  }
}

// --- Message Listeners ---

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'CHECK_VIDEO') {
    const videoId = getVideoId();
    if (videoId) {
      checkVideo(videoId, true); // Force check
    }
    sendResponse({ status: 'checking' });
  }
  return true;
});

// --- Keyboard Shortcuts ---

/**
 * Handle keyboard shortcuts:
 *   Esc     - Dismiss all overlays/banners
 *   I       - Toggle the AI info banner
 *   Shift+A - Trigger analysis on the current video
 */
document.addEventListener('keydown', (e) => {
  // Don't intercept when typing in an input/textarea/contenteditable
  const tag = e.target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || e.target.isContentEditable) return;

  if (e.key === 'Escape') {
    if (typeof hideAllOverlays === 'function') hideAllOverlays();
  }

  if (e.key === 'i' || e.key === 'I') {
    if (e.shiftKey || e.ctrlKey || e.altKey || e.metaKey) return;
    const banner = document.getElementById('ai-content-banner');
    if (banner) {
      banner.style.display = banner.style.display === 'none' ? 'block' : 'none';
    }
  }

  if (e.key === 'A' && e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey) {
    const videoId = getVideoId();
    if (videoId) {
      checkVideo(videoId, true);
    }
  }
});

// --- Ad Detection & Re-check ---

// Check for ads every second if we are analyzing or watching
setInterval(() => {
  if (isAdPlaying()) {
    // If ad is playing, ensure overlays are hidden
    const overlay = document.getElementById('safety-overlay');
    if (overlay && overlay.style.display !== 'none') {
      hideAllOverlays();
    }
  } else {
    // If ad finished and we had a dangerous video, re-show overlay?
    // For now, simpler to just let the user re-trigger if needed, 
    // or rely on checkVideo logic which prevents duplicate checks within 30s.
    // Ideally we'd store state "wasCovered" and restore it.
  }
}, 1000);

// Start
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
