/**
 * YouTube Safety Inspector - Content Script Entry Point
 * Copyright (c) 2026 beautifulplanet
 * Licensed under MIT License
 * 
 * This file coordinates:
 * 1. utils.js - Helper functions
 * 2. modes.js - Mode system
 * 3. sidebar.js - Analysis hub sidebar (two-state: chill/alert)
 * 4. overlay.js - Warning overlay
 * 5. analysis.js - Core analysis logic
 */

console.log(`🛡️ Safety Inspector v${chrome.runtime.getManifest().version} loaded`);

// --- Initialization ---

/** Initialize the content script: set up URL observers and check current page. */
async function init() {
  try {
    console.log('\ud83d\udee1\ufe0f init() starting on:', location.href);
    // YouTube is a Single Page App (SPA), so we need to watch for URL changes
    observeUrlChanges();

    // Initialize the sidebar (Shadow DOM, loads CSS)
    // Retry if createSidebar isn't defined yet (script load order race)
    let sidebarReady = false;
    for (let attempt = 0; attempt < 20; attempt++) {
      if (typeof createSidebar === 'function') {
        await createSidebar();
        sidebarReady = true;
        break;
      }
      await new Promise(r => setTimeout(r, 200));
    }
    if (!sidebarReady) {
      console.error('🛡️ createSidebar never became available');
      return;
    }
    console.log('🛡️ Sidebar created successfully');

    // Initial check if we landed directly on a video
    const videoId = getVideoId();
    console.log('🛡️ Video ID on init:', videoId);
    if (videoId) {
      // Show sidebar immediately so user sees something
      if (typeof onNavigationForSidebar === 'function') {
        onNavigationForSidebar(videoId);
      }

      // Wait for YouTube DOM to hydrate, then check: ad first, then analyze
      setTimeout(() => {
        if (typeof isAdPlaying === 'function' && isAdPlaying()) {
          // Pre-roll ad is playing — show Ad state;
          // the ad-check interval will trigger analysis when it ends
          console.log('🛡️ Pre-roll ad detected on init — waiting for it to finish');
          if (typeof setSidebarMode === 'function') setSidebarMode('ad');
        } else {
          checkVideo(videoId, true); // No ad — analyze immediately
        }
      }, 2500);
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
      console.log('🛡️ yt-navigate-finish fired:', location.href);
      debouncedUrlChange(location.href);
    });

    // popstate covers browser back/forward
    window.addEventListener('popstate', () => {
      debouncedUrlChange(location.href);
    });

  // URL polling fallback — catches SPA navigations even if yt-navigate-finish doesn't fire
    setInterval(() => {
      try {
        if (!(chrome.runtime && chrome.runtime.id)) return; // context dead
      } catch { return; }
      if (location.href !== lastUrl) {
        console.log('🛡️ URL change detected by polling:', location.href);
        debouncedUrlChange(location.href);
      }
    }, 1000);
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
    console.log('\ud83d\udee1\ufe0f URL changed to:', url);
    // Always hide overlays on navigation
    if (typeof hideAllOverlays === 'function') hideAllOverlays();

    // Check if it's a video
    const videoId = getVideoId();
    if (videoId) {
      // Give YouTube a moment to update the DOM
      setTimeout(() => {
        // Force fresh analysis on navigation (bypass cache for new video)
        checkVideo(videoId, true);
      }, 1000);
    }

    // Update sidebar visibility based on current page
    if (typeof onNavigationForSidebar === 'function') {
      onNavigationForSidebar(videoId);
    }
  } catch (err) {
    console.error('🛡️ Error in onUrlChange:', err);
  }
}

// --- Message Listeners ---

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  try {
    if (!(chrome.runtime && chrome.runtime.id)) return; // context dead
  } catch { return; }
  if (request.type === 'CHECK_VIDEO') {
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
let _adCheckInterval = null;
let _adWasPlaying = false;

function startAdCheckInterval() {
  if (_adCheckInterval) clearInterval(_adCheckInterval);
  _adCheckInterval = setInterval(() => {
    try {
      if (!(chrome.runtime && chrome.runtime.id)) { clearInterval(_adCheckInterval); return; }
    } catch { clearInterval(_adCheckInterval); return; }
    const adNow = isAdPlaying();
    
    if (adNow && !_adWasPlaying) {
      // Ad just started — show "Ad Playing" and hide any analysis results
      console.log('🛡️ Ad detected — showing ad state');
      if (typeof hideAllOverlays === 'function') hideAllOverlays();
      if (typeof setSidebarMode === 'function') {
        setSidebarMode('ad');
      }
    } else if (!adNow && _adWasPlaying) {
      // Ad just ended — NOW trigger fresh analysis for the actual video
      console.log('🛡️ Ad ended — triggering video analysis');
      const videoId = getVideoId();
      if (videoId && typeof checkVideo === 'function') {
        // Force fresh analysis: the video hasn't been analyzed yet (we deferred)
        checkVideo(videoId, true);
      } else if (typeof SIDEBAR_STATE !== 'undefined' && SIDEBAR_STATE.currentResults) {
        // Fallback: restore previous results if checkVideo isn't available
        if (typeof updateSidebarWithResults === 'function') {
          updateSidebarWithResults(SIDEBAR_STATE.currentResults);
        }
      }
    }
    
    _adWasPlaying = adNow;
  }, 1000);
}

// Start
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => { init(); startAdCheckInterval(); });
} else {
  init();
  startAdCheckInterval();
}
