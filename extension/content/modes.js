/**
 * YouTube Safety Inspector - Mode System
 * Copyright (c) 2026 beautifulplanet
 * Licensed under MIT License
 *
 * Reads video data from the bridge element populated by bridge.js
 * (which runs in the page's MAIN world and can access ytInitialData).
 *
 * Modes:
 *   - Subject (🎯) — Related videos from YouTube's sidebar data
 *   - Random  (🎲) — Shuffled mix of recommendations
 *   - Data    (📊) — Current video analytics/metadata
 *   - Learn   (🎓) — Tutorial/how-to filtered results
 */

/* global getVideoTitle, getChannelName, getVideoDescription */

// ═══════════════════════════════════════════════
// Bridge Data Access
// ═══════════════════════════════════════════════

// Bridge ID is randomized per page load; read from the attribute set by bridge.js
function _getBridgeId() {
  return document.documentElement.getAttribute('data-ysi-bridge') || '';
}

/**
 * Read related videos from the bridge element.
 * bridge.js (MAIN world) writes JSON to data-videos attribute.
 *
 * @param {number} [limit=20] Max items
 * @returns {Object[]} Array of video objects
 */
function readBridgeVideos(limit = 20) {
  const bridgeId = _getBridgeId();
  const bridge = bridgeId ? document.getElementById(bridgeId) : null;
  if (!bridge) {
    console.warn('🛡️ Bridge element not found');
    return [];
  }

  const raw = bridge.getAttribute('data-videos');
  if (!raw) {
    console.warn('🛡️ Bridge has no data-videos');
    return [];
  }

  try {
    const videos = JSON.parse(raw);
    if (!Array.isArray(videos)) return [];
    console.log(`🛡️ Bridge: read ${videos.length} videos`);

    // Strict 11-char YouTube video ID pattern
    const VALID_VID = /^[a-zA-Z0-9_-]{11}$/;

    // Sanitize & validate each entry from the untrusted MAIN-world bridge
    return videos.slice(0, limit)
      .filter(v => v && typeof v.videoId === 'string' && VALID_VID.test(v.videoId))
      .map(v => ({
        videoId: v.videoId,
        title: typeof v.title === 'string' ? v.title.slice(0, 200) : '',
        channel: typeof v.channel === 'string' ? v.channel.slice(0, 100) : '',
        thumbnail: `https://i.ytimg.com/vi/${v.videoId}/mqdefault.jpg`,
        duration: typeof v.duration === 'string' ? v.duration.slice(0, 20) : '',
        viewCount: parseViewCountText(typeof v.viewText === 'string' ? v.viewText : ''),
        publishedText: typeof v.publishedText === 'string' ? v.publishedText.slice(0, 50) : '',
      }));
  } catch (e) {
    console.error('🛡️ Bridge parse error:', e);
    return [];
  }
}

/**
 * Read current video metadata from the bridge element.
 * @returns {Object|null}
 */
function readBridgeMeta() {
  const bridgeId = _getBridgeId();
  const bridge = bridgeId ? document.getElementById(bridgeId) : null;
  if (!bridge) return null;

  const raw = bridge.getAttribute('data-meta');
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null;

    // Sanitize untrusted MAIN-world data: only allow expected string fields, truncated
    return {
      viewText:       typeof parsed.viewText === 'string'       ? parsed.viewText.slice(0, 100)       : '',
      dateText:       typeof parsed.dateText === 'string'       ? parsed.dateText.slice(0, 100)       : '',
      subscriberText: typeof parsed.subscriberText === 'string' ? parsed.subscriberText.slice(0, 100) : '',
    };
  } catch (_e) {
    return null;
  }
}

/**
 * Wait for the bridge to have actual video data (count > 0).
 * bridge.js retries on its own, so we poll for data-count attribute.
 *
 * @param {number} [timeoutMs=30000] Max wait
 * @returns {Promise<boolean>}
 */
function waitForBridge(timeoutMs = 30000) {
  return new Promise((resolve) => {
    function hasBridgeData() {
      const bridgeId = _getBridgeId();
      const bridge = bridgeId ? document.getElementById(bridgeId) : null;
      if (!bridge) return false;
      const count = parseInt(bridge.getAttribute('data-count') || '0', 10);
      return count > 0;
    }

    // Check immediately
    if (hasBridgeData()) {
      console.log('🛡️ Bridge data available immediately');
      resolve(true);
      return;
    }

    // Listen for the custom event from bridge.js
    const handler = (e) => {
      if (e.detail && e.detail.count > 0) {
        document.removeEventListener('ysi-data-ready', handler);
        clearTimeout(timer);
        clearInterval(poll);
        console.log('🛡️ Bridge data ready via event:', e.detail.count, 'videos');
        resolve(true);
      }
    };
    document.addEventListener('ysi-data-ready', handler);

    // Also poll in case event fires before listener is set up
    const poll = setInterval(() => {
      if (hasBridgeData()) {
        clearInterval(poll);
        clearTimeout(timer);
        document.removeEventListener('ysi-data-ready', handler);
        console.log('🛡️ Bridge data found via polling');
        resolve(true);
      }
    }, 600);

    const timer = setTimeout(() => {
      clearInterval(poll);
      document.removeEventListener('ysi-data-ready', handler);
      const hasData = hasBridgeData();
      console.warn('🛡️ Bridge wait timed out after', timeoutMs, 'ms, hasData:', hasData);
      resolve(hasData);
    }, timeoutMs);
  });
}

// ═══════════════════════════════════════════════
// Data Mode: Current Video Metadata
// ═══════════════════════════════════════════════

/**
 * Extract current video metadata from bridge + DOM.
 * @returns {Object|null}
 */
function scrapeCurrentVideoData() {
  try {
    const params = new URLSearchParams(window.location.search);
    const rawId = params.get('v');
    // Validate video ID: exactly 11 chars, alphanumeric + hyphen/underscore
    if (!rawId || !/^[a-zA-Z0-9_-]{11}$/.test(rawId)) return null;
    const videoId = rawId;

    // Read bridge meta (from ytInitialData via MAIN world)
    const meta = readBridgeMeta() || {};
    let viewCount = parseViewCountText(meta.viewText || '');
    let publishedText = meta.dateText || '';
    let subscriberText = meta.subscriberText || '';

    // DOM fallbacks
    const title = getVideoTitle();
    const channel = getChannelName();
    const description = getVideoDescription();

    if (!viewCount) {
      const viewEl = document.querySelector(
        'ytd-watch-metadata #info-container yt-formatted-string span, ' +
        'ytd-watch-metadata .view-count, ' +
        '#info-text .view-count, #count .ytd-video-primary-info-renderer'
      );
      viewCount = parseViewCountText(viewEl?.textContent?.trim() || '');
    }

    const likeBtn = document.querySelector(
      'like-button-view-model button, ' +
      '#segmented-like-button button, ' +
      'ytd-toggle-button-renderer #text'
    );
    const likeText = likeBtn?.getAttribute('aria-label') || likeBtn?.textContent?.trim() || '';
    const likeCount = parseViewCountText(likeText);

    if (!subscriberText) {
      const subEl = document.querySelector('#owner-sub-count, #subscriber-count');
      subscriberText = subEl?.textContent?.trim() || '';
    }

    if (!publishedText) {
      const dateEl = document.querySelector(
        '#info-strings yt-formatted-string, #info span:nth-child(3)'
      );
      publishedText = dateEl?.textContent?.trim() || '';
    }

    return {
      videoId,
      title,
      channel,
      description,
      thumbnail: `https://i.ytimg.com/vi/${videoId}/maxresdefault.jpg`,
      viewCount,
      likeCount,
      subscriberText,
      publishedText,
      publishedAt: null,
    };
  } catch (_e) {
    return null;
  }
}

// ═══════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════

/**
 * Parse "1.2M views" or "1,234,567 views" into a number.
 */
function parseViewCountText(text) {
  if (!text) return 0;
  const clean = text.replace(/[^0-9.KMBkmb,]/g, '').trim();
  if (!clean) return 0;

  const lower = clean.toLowerCase();
  let num = parseFloat(lower.replace(/,/g, ''));
  if (isNaN(num)) return 0;

  if (lower.includes('b')) num *= 1_000_000_000;
  else if (lower.includes('m')) num *= 1_000_000;
  else if (lower.includes('k')) num *= 1_000;

  return Math.round(num);
}

/**
 * Fisher-Yates shuffle.
 */
function shuffleArray(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

// ═══════════════════════════════════════════════
// Mode Implementations
// ═══════════════════════════════════════════════

const ModeHandlers = {

  // Subject Mode (🎯) — Related videos
  subject: {
    async fetchContent(context) {
      if (!context.videoId) return [];
      await waitForBridge(12000);

      const related = readBridgeVideos(12);
      if (related.length === 0) return [];

      return related
        .filter(v => v.videoId !== context.videoId)
        .slice(0, 8);
    },
    getEmptyMessage() {
      return 'Watch a video to find related content';
    }
  },

  // Random Mode (🎲) — Shuffled recommendations
  random: {
    async fetchContent(context) {
      if (!context.videoId) return [];
      await waitForBridge(12000);

      const related = readBridgeVideos(20);
      if (related.length === 0) return [];

      const filtered = related.filter(v => v.videoId !== context.videoId);
      shuffleArray(filtered);

      const historyIds = new Set((context.history || []).map(h => h.videoId));
      const fresh = filtered.filter(v => !historyIds.has(v.videoId));
      return fresh.length > 0 ? fresh.slice(0, 8) : filtered.slice(0, 8);
    },
    getEmptyMessage() {
      return 'Discovering content...';
    }
  },

  // Data Mode (📊) — Current video analytics
  data: {
    async fetchContent(context) {
      if (!context.videoId) return [];
      await waitForBridge(5000);
      await new Promise(r => setTimeout(r, 800));

      const videoData = scrapeCurrentVideoData();
      if (!videoData) return [];

      return [{
        videoId: videoData.videoId,
        title: videoData.title,
        channel: videoData.channel,
        thumbnail: videoData.thumbnail,
        viewCount: videoData.viewCount,
        likeCount: videoData.likeCount,
        subscriberText: videoData.subscriberText,
        publishedText: videoData.publishedText,
        description: videoData.description,
        isDataView: true,
      }];
    },
    getEmptyMessage() {
      return 'Watch a video to see analytics';
    }
  },

  // Learn Mode (🎓) — Tutorial-filtered results
  learn: {
    async fetchContent(context) {
      if (!context.videoId) return [];
      await waitForBridge(12000);

      const related = readBridgeVideos(20);
      if (related.length === 0) return [];

      const tutorialKeywords = [
        'how to', 'tutorial', 'guide', 'learn', 'beginner',
        'explained', 'tips', 'step by step', 'course', 'lesson',
        'basics', 'masterclass', 'training', 'for beginners',
        'walkthrough', 'deep dive', 'breakdown', 'review',
      ];

      const tutorials = related.filter(v => {
        const lower = v.title.toLowerCase();
        return tutorialKeywords.some(kw => lower.includes(kw));
      });

      if (tutorials.length >= 2) {
        return tutorials.slice(0, 8);
      }

      const latter = related.slice(Math.floor(related.length / 2));
      return latter
        .filter(v => v.videoId !== context.videoId)
        .slice(0, 8);
    },
    getEmptyMessage() {
      return 'Watch a video to find tutorials';
    }
  }
};

/**
 * Get the handler for a given mode.
 */
function getModeHandler(modeName) {
  return ModeHandlers[modeName] || ModeHandlers.data;
}
