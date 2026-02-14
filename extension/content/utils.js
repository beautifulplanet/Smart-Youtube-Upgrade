/**
 * YouTube Safety Inspector - Content Script Utilities
 * Copyright (c) 2026 beautifulplanet
 * Licensed under MIT License
 */

/**
 * Get the current video ID from the URL
 * Handles both regular videos (watch?v=) and Shorts (/shorts/)
 * @returns {string|null} Video ID or null if not found
 */
function getVideoId() {
  const url = location.href;
  
  // Regular video: youtube.com/watch?v=VIDEO_ID
  const watchMatch = url.match(/[?&]v=([^&]+)/);
  if (watchMatch) return watchMatch[1];
  
  // Shorts: youtube.com/shorts/VIDEO_ID
  const shortsMatch = url.match(/\/shorts\/([^/?]+)/);
  if (shortsMatch) return shortsMatch[1];
  
  return null;
}

/**
 * Detect if a YouTube ad is currently playing
 * ONLY for regular videos - Shorts don't have pre-roll ads the same way
 * @returns {boolean} True if ad is playing
 */
function isAdPlaying() {
  // NEVER report ad playing on Shorts - they use different ad format
  const isShorts = location.pathname.includes('/shorts/');
  if (isShorts) {
    return false;
  }
  
  // Method 1: Check video player class for ad state (most reliable for regular videos)
  const videoPlayer = document.querySelector('.html5-video-player');
  if (videoPlayer && videoPlayer.classList.contains('ad-showing')) {
    return true;
  }

  // Method 2: Check for "Skip Ad" button (definitive signal)
  const skipButton = document.querySelector('.ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button');
  if (skipButton && skipButton.offsetParent !== null) {
    return true;
  }

  // Method 3: Check for ad preview countdown
  const adPreview = document.querySelector('.ytp-ad-preview-container');
  if (adPreview && adPreview.offsetParent !== null) {
    return true;
  }

  // Method 4: Check for ad overlay elements
  const adOverlay = document.querySelector('.ytp-ad-player-overlay');
  if (adOverlay && adOverlay.offsetParent !== null) {
    return true;
  }
  
  return false;
}

/**
 * Scrape video title from YouTube page
 * @returns {string} Video title
 */
function getVideoTitle() {
  const isShorts = location.pathname.includes('/shorts/');
  
  if (isShorts) {
    // Shorts - try multiple selectors
    // 1. Reel overlay title
    const reelTitle = document.querySelector('ytd-reel-video-renderer[is-active] h2.ytd-reel-player-header-renderer');
    if (reelTitle?.textContent?.trim()) return reelTitle.textContent.trim();
    
    // 2. Shorts player header
    const shortsHeader = document.querySelector('ytd-reel-video-renderer[is-active] #shorts-player-title, ytd-shorts h2');
    if (shortsHeader?.textContent?.trim()) return shortsHeader.textContent.trim();
    
    // 3. Try meta tags
    const metaTitle = document.querySelector('meta[property="og:title"], meta[name="title"]');
    if (metaTitle?.content?.trim()) return metaTitle.content.trim();
    
    // 4. Fallback: document title
    const docTitle = document.title.replace(' - YouTube', '').replace('#shorts', '').trim();
    if (docTitle) return docTitle;
  }
  
  // Regular video selectors
  const titleEl = document.querySelector('h1.ytd-watch-metadata yt-formatted-string, h1.title yt-formatted-string, #title h1 yt-formatted-string');
  if (titleEl?.textContent?.trim()) return titleEl.textContent.trim();
  
  // Fallback to meta or document title
  const metaTitle = document.querySelector('meta[property="og:title"], meta[name="title"]');
  if (metaTitle?.content?.trim()) return metaTitle.content.trim();
  
  return document.title.replace(' - YouTube', '').trim();
}

/**
 * Scrape channel name from YouTube page
 * @returns {string} Channel name
 */
function getChannelName() {
  const isShorts = location.pathname.includes('/shorts/');
  
  if (isShorts) {
    // Shorts - try multiple selectors
    // 1. Active reel channel name
    const reelChannel = document.querySelector('ytd-reel-video-renderer[is-active] ytd-channel-name a, ytd-reel-video-renderer[is-active] #channel-name a');
    if (reelChannel?.textContent?.trim()) return reelChannel.textContent.trim();
    
    // 2. Shorts overlay channel
    const shortsChannel = document.querySelector('ytd-reel-player-overlay-renderer #channel-name a, .ytd-reel-player-header-renderer #channel-name');
    if (shortsChannel?.textContent?.trim()) return shortsChannel.textContent.trim();
    
    // 3. Try any visible channel name in shorts
    const anyChannel = document.querySelector('[is-active] #channel-name, ytd-shorts #channel-name a');
    if (anyChannel?.textContent?.trim()) return anyChannel.textContent.trim();
    
    // 4. Meta tag fallback
    const metaChannel = document.querySelector('meta[name="author"], link[itemprop="name"]');
    if (metaChannel?.content?.trim()) return metaChannel.content.trim();
  }
  
  // Regular video - channel link
  const channelEl = document.querySelector('#channel-name a, ytd-channel-name a, #owner-name a, #upload-info ytd-channel-name a');
  if (channelEl?.textContent?.trim()) return channelEl.textContent.trim();
  
  return '';
}

/**
 * Scrape video description (first 500 chars)
 * @returns {string} Video description
 */
function getVideoDescription() {
  const isShorts = location.pathname.includes('/shorts/');
  
  if (isShorts) {
    // Shorts often don't have visible descriptions, try meta
    const metaDesc = document.querySelector('meta[property="og:description"], meta[name="description"]');
    if (metaDesc?.content?.trim()) return metaDesc.content.trim().substring(0, 500);
    return '';
  }
  
  const descEl = document.querySelector('#description-inner, ytd-text-inline-expander #snippet-text, #description yt-formatted-string');
  if (descEl?.textContent?.trim()) return descEl.textContent.trim().substring(0, 500);
  
  // Fallback to meta description
  const metaDesc = document.querySelector('meta[property="og:description"], meta[name="description"]');
  if (metaDesc?.content?.trim()) return metaDesc.content.trim().substring(0, 500);
  
  return '';
}

/**
 * Add YouTube API attribution (required by YouTube TOS)
 * @param {HTMLElement} container The container to append attribution to
 */
function addYouTubeAttribution(container) {
  // Check if attribution already exists
  if (container.querySelector('.yt-api-attribution')) return;
  
  const attr = document.createElement('div');
  attr.className = 'yt-api-attribution';
  attr.innerHTML = '📊 Data provided by <a href="https://developers.google.com/youtube" target="_blank" style="color: #888; text-decoration: underline;">YouTube Data API</a>';
  attr.style.cssText = 'font-size: 10px; color: #666; text-align: center; padding: 8px; margin-top: auto; border-top: 1px solid #333;';
  container.appendChild(attr);
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text Text to escape
 * @returns {string} Escaped HTML
 */
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
