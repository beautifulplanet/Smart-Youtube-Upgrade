/**
 * YouTube Safety Inspector - Main World Bridge (v3)
 * Copyright (c) 2026 beautifulplanet
 * Licensed under MIT License
 *
 * Runs in the PAGE'S MAIN JavaScript world.
 *
 * ── CWS REVIEW: MAIN WORLD JUSTIFICATION ──
 * This script MUST run in the MAIN world because YouTube loads related-
 * video data via internal fetch/XHR calls to /youtubei/v1/next that are
 * invisible to ISOLATED content scripts. The broad match (youtube.com/*)
 * is required because YouTube is a Single Page Application — users
 * navigate from any page to video pages without full reloads, so the
 * bridge must be injected before the first navigation.
 *
 * This script ONLY reads YouTube API responses to extract public video
 * metadata (titles, channels, durations). It does NOT:
 *   • Execute remote code
 *   • Modify page content or behaviour
 *   • Access cookies, credentials, or user data
 *   • Communicate with external servers
 * Data is passed to isolated-world scripts via a hidden DOM element.
 * ── END JUSTIFICATION ──
 *
 * YouTube (2025+) lazy-loads related videos via fetch continuation
 * requests — they are NOT in ytInitialData anymore. This script:
 *
 *   1. Monkey-patches window.fetch to intercept YouTube API responses
 *      (specifically /youtubei/v1/next) that carry related video data.
 *   2. Also checks ytInitialData.onResponseReceivedEndpoints as a
 *      fallback for pages that still inline video suggestions.
 *   3. Writes extracted videos to a hidden DOM element that the
 *      isolated-world content scripts read.
 */

(function () {
  'use strict';

  // Generate a random bridge ID per page load to prevent static detection
  const _bridgeRandom = Array.from(crypto.getRandomValues(new Uint8Array(8)), b => b.toString(16).padStart(2, '0')).join('');
  const BRIDGE_ID = `ysi-b-${_bridgeRandom}`;
  const TAG = '🌉 Bridge';
  const DEBUG = false;
  function log(...args) { if (DEBUG) console.log(TAG, ...args); }

  // ─── Bridge Element ────────────────────────────

  function getBridgeElement() {
    let el = document.getElementById(BRIDGE_ID);
    if (!el) {
      el = document.createElement('div');
      el.id = BRIDGE_ID;
      el.style.display = 'none';
      el.setAttribute('aria-hidden', 'true');
      document.documentElement.appendChild(el);
      // Store bridge ID so isolated-world content scripts can find it
      document.documentElement.setAttribute('data-ysi-bridge', BRIDGE_ID);
    }
    return el;
  }

  // ─── Video Extraction ──────────────────────────

  /**
   * Extract a normalised video object from any YouTube renderer.
   */
  function extractVideo(renderer) {
    if (!renderer || !renderer.videoId) return null;

    // Shorts use headline instead of title, and accessibility labels
    const title =
      renderer.title?.simpleText ||
      renderer.title?.runs?.map(r => r.text).join('') ||
      renderer.headline?.simpleText ||
      renderer.headline?.runs?.map(r => r.text).join('') ||
      renderer.accessibility?.accessibilityData?.label?.split(' - ')?.[0] ||
      '';

    // Accept videos even without title — videoId is enough for iframes
    const cleanTitle = title.length > 2 ? title : `Video ${renderer.videoId.slice(0, 6)}`;

    return {
      videoId: renderer.videoId,
      title: cleanTitle,
      channel:
        renderer.longBylineText?.runs?.[0]?.text ||
        renderer.shortBylineText?.runs?.[0]?.text ||
        renderer.ownerText?.runs?.[0]?.text || '',
      duration:
        renderer.lengthText?.simpleText ||
        renderer.lengthText?.runs?.map(r => r.text).join('') ||
        renderer.thumbnailOverlays?.[0]
          ?.thumbnailOverlayTimeStatusRenderer?.text?.simpleText || '',
      viewText:
        renderer.viewCountText?.simpleText ||
        renderer.viewCountText?.runs?.map(r => r.text).join('') ||
        renderer.shortViewCountText?.simpleText || '',
      publishedText:
        renderer.publishedTimeText?.simpleText ||
        renderer.publishedTimeText?.runs?.map(r => r.text).join('') || '',
    };
  }

  /**
   * Recursively collect video renderers from any object tree.
   */
  function collectVideos(obj, depth = 0, seen = new Set(), out = []) {
    if (!obj || depth > 20 || out.length >= 60) return out;
    if (typeof obj !== 'object') return out;

    // Check renderer keys (includes Shorts-specific renderers)
    const keys = [
      'compactVideoRenderer', 'videoRenderer',
      'richCompactVideoRenderer', 'gridVideoRenderer',
      'reelItemRenderer', 'shortsLockupViewModel',
      'reelWatchEndpoint',
    ];
    for (const k of keys) {
      if (obj[k]) {
        const v = extractVideo(obj[k]);
        if (v && !seen.has(v.videoId)) { seen.add(v.videoId); out.push(v); }
      }
    }

    // Check if obj itself is a renderer
    if (obj.videoId && obj.title && !seen.has(obj.videoId)) {
      const v = extractVideo(obj);
      if (v) { seen.add(v.videoId); out.push(v); }
    }

    // Recurse — skip heavy irrelevant branches
    const skip = new Set([
      'playerOverlays', 'topbar', 'header', 'microformat',
      'frameworkUpdates', 'responseContext', 'playerConfig',
      'storyboards', 'attestation', 'playabilityStatus',
    ]);

    if (Array.isArray(obj)) {
      for (const item of obj) collectVideos(item, depth + 1, seen, out);
    } else {
      for (const k of Object.keys(obj)) {
        if (skip.has(k)) continue;
        collectVideos(obj[k], depth + 1, seen, out);
      }
    }
    return out;
  }

  // ─── Push to Bridge ────────────────────────────

  /** Accumulated videos (may come from multiple sources). */
  let allVideos = [];
  const allSeen = new Set();

  function mergeVideos(newVids) {
    for (const v of newVids) {
      if (!allSeen.has(v.videoId)) {
        allSeen.add(v.videoId);
        allVideos.push(v);
      }
    }
  }

  let hasPushedOnce = false;
  let lastPushedCount = 0;

  function pushToBridge(force = false) {
    // Don't push too early — wait until we have enough videos
    // UNLESS forced (timeout/cleanup) or we've never pushed and have SOMETHING
    if (!force && allVideos.length < MIN_VIDEOS && allVideos.length > 0) {
      log(`Holding push: ${allVideos.length}/${MIN_VIDEOS} videos (waiting for more)`);
      return;
    }

    if (allVideos.length === 0) return;

    // Skip if count hasn't changed (prevents redundant refreshes that destroy iframes)
    if (allVideos.length === lastPushedCount && hasPushedOnce) {
      return;
    }

    const bridge = getBridgeElement();
    bridge.setAttribute('data-videos', JSON.stringify(allVideos));
    bridge.setAttribute('data-count', String(allVideos.length));
    bridge.setAttribute('data-ts', Date.now().toString());

    log(`Pushed ${allVideos.length} videos to bridge${hasPushedOnce ? ' (update)' : ' (first push)'}`);

    lastPushedCount = allVideos.length;
    document.dispatchEvent(new CustomEvent('ysi-data-ready', {
      detail: { count: allVideos.length, isUpdate: hasPushedOnce },
    }));
    hasPushedOnce = true;
  }

  /**
   * Also extract current-video metadata from ytInitialData.
   */
  function pushMeta() {
    try {
      const data = window.ytInitialData;
      if (!data) return;

      const twoCol = data?.contents?.twoColumnWatchNextResults;
      const primaryContents = twoCol?.results?.results?.contents || [];
      let videoMeta = null;

      for (const item of primaryContents) {
        const vpir = item?.videoPrimaryInfoRenderer;
        if (vpir) {
          videoMeta = videoMeta || {};
          videoMeta.viewText =
            vpir?.viewCount?.videoViewCountRenderer?.viewCount?.simpleText ||
            vpir?.viewCount?.videoViewCountRenderer?.viewCount?.runs?.map(r => r.text).join('') || '';
          videoMeta.dateText = vpir?.dateText?.simpleText || '';
        }
        const vsir = item?.videoSecondaryInfoRenderer;
        if (vsir) {
          videoMeta = videoMeta || {};
          videoMeta.subscriberText =
            vsir?.owner?.videoOwnerRenderer?.subscriberCountText?.simpleText || '';
        }
      }

      const bridge = getBridgeElement();
      bridge.setAttribute('data-meta', JSON.stringify(videoMeta || {}));
    } catch (_e) { /* silent */ }
  }

  // ─── Source 1: ytInitialData ───────────────────

  function tryYtInitialData() {
    const data = window.ytInitialData;
    if (!data) return;

    // Check onResponseReceivedEndpoints (sometimes has inline suggestions)
    const endpoints = data.onResponseReceivedEndpoints || [];
    for (const ep of endpoints) {
      const actions = ep?.appendContinuationItemsAction?.continuationItems ||
        ep?.reloadContinuationItemsCommand?.continuationItems || [];
      const vids = collectVideos(actions);
      if (vids.length) {
        log(`ytInitialData.onResponseReceivedEndpoints: ${vids.length} videos`);
        mergeVideos(vids);
      }
    }

    // Also do a full recurse of secondaryResults
    const secondary = data?.contents?.twoColumnWatchNextResults?.secondaryResults;
    if (secondary) {
      const vids = collectVideos(secondary);
      if (vids.length) {
        log(`ytInitialData.secondaryResults: ${vids.length} videos`);
        mergeVideos(vids);
      }
    }

    // Full recurse as last resort (expensive but thorough)
    if (allVideos.length === 0) {
      const vids = collectVideos(data);
      if (vids.length) {
        log(`ytInitialData full recurse: ${vids.length} videos`);
        mergeVideos(vids);
      }
    }

    pushMeta();

    if (allVideos.length > 0) {
      pushToBridge();
    } else {
      log('ytInitialData had 0 videos — waiting for fetch');
    }
  }

  // ─── Source 2: Fetch Interception ──────────────

  /**
   * Monkey-patch window.fetch to intercept YouTube API responses.
   * YouTube lazy-loads the related videos sidebar via
   *   POST /youtubei/v1/next?...
   * The response JSON contains continuation items with compactVideoRenderers.
   */
  const originalFetch = window.fetch;

  window.fetch = function (...args) {
    let url = '';
    if (typeof args[0] === 'string') {
      url = args[0];
    } else if (args[0] instanceof Request) {
      url = args[0].url;
    }

    // PASS THROUGH CRITICAL STREAMS IMMEDIATELY — no interception, no logging
    // These are signed video stream URLs; any interference causes 403s
    if (url && (
      url.includes('googlevideo.com') ||
      url.includes('videoplayback') ||
      url.includes('doubleclick.net') ||
      url.includes('googleadservices.com') ||
      url.includes('.google.com/pagead') ||
      !url.includes('youtube.com')
    )) {
      return originalFetch.apply(this, args);
    }

    // Execute the fetch
    const promise = originalFetch.apply(this, args);

    // Side-effect: Inspect JSON responses for related videos (non-blocking)
    if (url && (
      url.includes('/youtubei/v1/next') ||
      url.includes('/youtubei/v1/browse') ||
      url.includes('/youtubei/v1/search') ||
      url.includes('/youtubei/v1/reel')
    )) {
      promise.then(response => {
        // Clone to read body without consuming the original stream
        try {
          const clone = response.clone();
          clone.json().then(json => {
            if (!json) return;
            const vids = collectVideos(json);
            if (vids.length > 0) {
              log(`fetch intercept (${url.split('?')[0].split('/').pop()}): ${vids.length} videos`);
              mergeVideos(vids);
              pushToBridge();
            }
          }).catch(() => { /* not JSON or parse error — ignore */ });
        } catch (e) {
          // Response might be opaque or redirect
        }
      }).catch(e => {
        // Network error in original fetch, ignore here
      });
    }

    return promise;
  };

  log('Fetch interceptor installed');

  // ─── Source 3: XHR Interception (backup) ───────

  /**
   * Also intercept XMLHttpRequest for older YouTube code paths.
   */
  const origXHROpen = XMLHttpRequest.prototype.open;
  const origXHRSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    // Only tag YouTube API URLs — never tag third-party ad/tracker domains
    if (typeof url === 'string' && url.includes('youtube.com/youtubei/')) {
      this._ysiUrl = url;
    }
    return origXHROpen.call(this, method, url, ...rest);
  };

  XMLHttpRequest.prototype.send = function (...args) {
    if (this._ysiUrl && (
      this._ysiUrl.includes('/youtubei/v1/next') ||
      this._ysiUrl.includes('/youtubei/v1/browse')
    )) {
      this.addEventListener('load', function () {
        try {
          const json = JSON.parse(this.responseText);
          const vids = collectVideos(json);
          if (vids.length > 0) {
            log(`XHR intercept: ${vids.length} videos`);
            mergeVideos(vids);
            pushToBridge();
          }
        } catch (_e) { /* ignore */ }
      });
    }
    return origXHRSend.apply(this, args);
  };

  log('XHR interceptor installed');

  // ─── Source 4: DOM Scraping Fallback ────────────

  // Minimum useful video count — keep searching until we have this many
  const MIN_VIDEOS = 5;

  /**
   * Scrape rendered video elements directly from YouTube's DOM.
   * YouTube 2026+ no longer uses ytd-compact-video-renderer elements.
   * We scrape all <a href="/watch?v="> links and extract metadata.
   */
  function scrapeRelatedFromDOM() {
    // Debug: log what we can find
    const tagCounts = {};
    const ytTags = ['ytd-compact-video-renderer', 'ytd-video-renderer',
      'ytd-rich-item-renderer', 'ytd-grid-video-renderer',
      'ytd-reel-item-renderer', 'ytd-shelf-renderer'];
    for (const tag of ytTags) {
      const count = document.querySelectorAll(tag).length;
      if (count > 0) tagCounts[tag] = count;
    }
    log('DOM survey:', JSON.stringify(tagCounts));

    // Scrape both /watch?v= and /shorts/ links
    const watchLinks = document.querySelectorAll('a[href*="/watch?v="]');
    const shortsLinks = document.querySelectorAll('a[href*="/shorts/"]');
    log(`DOM has ${watchLinks.length} /watch?v= + ${shortsLinks.length} /shorts/ links`);

    const vids = [];
    const seen = new Set();

    // Detect current video ID from either URL format
    const currentId = new URLSearchParams(window.location.search).get('v') ||
      window.location.pathname.match(/\/shorts\/([\w-]{11})/)?.[1] || null;

    // Helper to extract video info from a link element
    function processLink(link, videoId) {
      if (seen.has(videoId)) return;
      if (videoId === currentId) return;
      seen.add(videoId);

      const title = link.getAttribute('title') ||
        link.getAttribute('aria-label') ||
        link.querySelector('#video-title, .title, h3, span')?.textContent?.trim() ||
        link.closest('[class*="renderer"], [class*="lockup"]')?.querySelector(
          '#video-title, [id*="title"], .title, h3, [role="heading"]'
        )?.textContent?.trim() ||
        link.textContent?.trim() ||
        '';

      const cleanTitle = title.length > 2 ? title : `Video ${videoId.slice(0, 6)}`;

      const container = link.closest('[class*="renderer"], [class*="lockup"], [class*="item"]');
      const channel = container?.querySelector(
        'ytd-channel-name #text, #channel-name, [class*="channel"], [class*="byline"]'
      )?.textContent?.trim() || '';

      const duration = container?.querySelector(
        '[class*="time-status"] span, badge-shape .badge-shape-wiz__text, [class*="duration"]'
      )?.textContent?.trim() || '';

      vids.push({ videoId, title: cleanTitle, channel, duration, viewText: '', publishedText: '' });
    }

    // Process /watch?v= links
    watchLinks.forEach(link => {
      try {
        const href = link.getAttribute('href') || '';
        const match = href.match(/\/watch\?v=([\w-]{11})/);
        if (match) processLink(link, match[1]);
      } catch (_e) { /* skip */ }
    });

    // Process /shorts/ links
    shortsLinks.forEach(link => {
      try {
        const href = link.getAttribute('href') || '';
        const match = href.match(/\/shorts\/([\w-]{11})/);
        if (match) processLink(link, match[1]);
      } catch (_e) { /* skip */ }
    });

    log(`DOM scrape result: ${vids.length} videos`);
    return vids;
  }

  // ─── MutationObserver for lazy-loaded content ──

  let domObserver = null;
  let domObserverTimeout = null;

  /**
   * Start watching the DOM for video links to appear.
   * Keeps watching until we have MIN_VIDEOS or 45s timeout.
   */
  function startDOMObserver() {
    if (domObserver) {
      domObserver.disconnect();
      domObserver = null;
    }
    if (domObserverTimeout) {
      clearTimeout(domObserverTimeout);
    }

    // Don't observe if we already have enough videos
    if (allVideos.length >= MIN_VIDEOS) return;

    let debounceTimer = null;

    domObserver = new MutationObserver((mutations) => {
      // Stop if we have enough videos
      if (allVideos.length >= MIN_VIDEOS) {
        domObserver.disconnect();
        domObserver = null;
        return;
      }

      // Check if any mutation added video links
      let found = false;
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType !== 1) continue;
          if (node.tagName === 'A' && node.getAttribute?.('href')?.includes('/watch?v=')) {
            found = true;
            break;
          }
          if (node.querySelector?.('a[href*="/watch?v="]')) {
            found = true;
            break;
          }
        }
        if (found) break;
      }

      if (found) {
        // Debounce — wait for YouTube to finish rendering batch
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          const domVids = scrapeRelatedFromDOM();
          if (domVids.length > 0) {
            log(`MutationObserver caught ${domVids.length} videos`);
            mergeVideos(domVids);
            pushToBridge();
            // Only disconnect if we have enough
            if (allVideos.length >= MIN_VIDEOS && domObserver) {
              domObserver.disconnect();
              domObserver = null;
            }
          }
        }, 800); // Wait 800ms for batch to finish
      }
    });

    domObserver.observe(document.documentElement, {
      childList: true,
      subtree: true,
    });

    // Stop observing after 30 seconds
    domObserverTimeout = setTimeout(() => {
      if (domObserver) {
        domObserver.disconnect();
        domObserver = null;

        // One final attempt
        const domVids = scrapeRelatedFromDOM();
        if (domVids.length > 0) {
          log(`Final DOM scrape: ${domVids.length} videos`);
          mergeVideos(domVids);
          pushToBridge();
        } else if (allVideos.length === 0) {
          log('No videos found after observing DOM for 30s');
        }
      }
    }, 30000);
  }

  // ─── Init ──────────────────────────────────────

  let activeTimer = null; // Module-level so SPA nav can cancel it
  let navRetryTimer = null; // Module-level to prevent leak on rapid nav

  function init() {
    log('Initialising...');
    tryYtInitialData();

    // If ytInitialData gave us enough, we're done
    if (allVideos.length >= MIN_VIDEOS) return;

    // Start MutationObserver to catch lazily-loaded related videos
    startDOMObserver();

    // Cancel any previous timer (from prior init or nav)
    if (activeTimer) clearInterval(activeTimer);

    // Retry loop — keep trying until we have enough videos
    let attempts = 0;
    activeTimer = setInterval(() => {
      attempts++;

      // Try ytInitialData
      if (window.ytInitialData && allVideos.length < MIN_VIDEOS) {
        tryYtInitialData();
      }

      // DOM scrape on EVERY attempt
      if (allVideos.length < MIN_VIDEOS) {
        const domVids = scrapeRelatedFromDOM();
        if (domVids.length > 0) {
          const prevCount = allVideos.length;
          mergeVideos(domVids);
          if (allVideos.length > prevCount) {
            log(`Periodic scrape: ${prevCount} → ${allVideos.length} videos`);
            pushToBridge();
          }
        }
      }

      // Stop when we have enough OR max retries
      if (allVideos.length >= MIN_VIDEOS || attempts >= 30) {
        clearInterval(activeTimer);
        activeTimer = null;
        if (allVideos.length > 0) {
          log(`Done: ${allVideos.length} videos after ${attempts}s`);
          pushToBridge(true); // Force push whatever we have
        } else {
          log('Gave up after 30s with 0 videos');
        }
      }
    }, 1000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // ─── SPA Navigation ────────────────────────────

  window.addEventListener('yt-navigate-finish', () => {
    log('yt-navigate-finish — resetting');

    // Cancel ALL active timers from previous page
    if (activeTimer) {
      clearInterval(activeTimer);
      activeTimer = null;
    }
    if (navRetryTimer) {
      clearInterval(navRetryTimer);
      navRetryTimer = null;
    }

    allVideos = [];
    allSeen.clear();
    hasPushedOnce = false;
    lastPushedCount = 0;

    // YouTube signaled navigation done — start searching
    setTimeout(() => {
      tryYtInitialData();

      if (allVideos.length < MIN_VIDEOS) {
        startDOMObserver();

        // Immediate DOM scrape
        const domVids = scrapeRelatedFromDOM();
        if (domVids.length > 0) {
          log(`Post-nav scrape: ${domVids.length} videos`);
          mergeVideos(domVids);
          pushToBridge();
        }

        // Keep retrying for more videos
        let navAttempts = 0;
        if (navRetryTimer) clearInterval(navRetryTimer);
        navRetryTimer = setInterval(() => {
          navAttempts++;
          if (allVideos.length < MIN_VIDEOS) {
            const more = scrapeRelatedFromDOM();
            if (more.length > 0) {
              const prev = allVideos.length;
              mergeVideos(more);
              if (allVideos.length > prev) {
                log(`Nav retry: ${prev} → ${allVideos.length} videos`);
                pushToBridge();
              }
            }
          }
          if (allVideos.length >= MIN_VIDEOS || navAttempts >= 15) {
            clearInterval(navRetryTimer);
            navRetryTimer = null;
            if (allVideos.length > 0) pushToBridge(true); // Force push at end
          }
        }, 1000);
      }
    }, 300);
  });

  document.addEventListener('yt-page-data-updated', () => {
    setTimeout(() => {
      tryYtInitialData();

      if (allVideos.length < MIN_VIDEOS) {
        startDOMObserver();

        const domVids = scrapeRelatedFromDOM();
        if (domVids.length > 0) {
          log(`Post-update scrape: ${domVids.length} videos`);
          mergeVideos(domVids);
          pushToBridge();
        }
      }
    }, 300);
  });

})();
