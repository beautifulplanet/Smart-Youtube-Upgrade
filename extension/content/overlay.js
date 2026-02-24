/**
 * YouTube Safety Inspector - Overlay & UI Management
 * Copyright (c) 2026 beautifulplanet
 * Licensed under MIT License
 */

/**
 * Hide all safety overlays (used during ads)
 */
function hideAllOverlays() {
  const overlay = document.getElementById('safety-overlay');
  const aiBanner = document.getElementById('ai-content-banner');
  const aiFlash = document.getElementById('ai-flash-overlay');

  if (overlay) overlay.style.display = 'none';
  if (aiBanner) aiBanner.style.display = 'none';
  if (aiFlash) aiFlash.style.display = 'none';
}

/** Inject the safety warning overlay with score, warnings, and alternatives. */
function injectOverlay() {
  // Remove existing if any
  const existing = document.getElementById('safety-overlay');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.id = 'safety-overlay';
  overlay.className = 'safety-overlay hidden'; // Starts hidden

  // Note: Most styles are now in content.css

  overlay.innerHTML = `
    <div class="overlay-content">
      <div style="display: flex; gap: 40px; align-items: flex-start; flex-wrap: wrap; justify-content: center;">
        
        <!-- Left side: Warning -->
        <div style="flex: 1; min-width: 300px; max-width: 400px;">
          <div class="overlay-icon">⚠️</div>
          <div id="safety-score" class="overlay-score">--</div>
          <div class="overlay-title">SAFETY WARNING</div>
          <div class="overlay-subtitle">Community flagged dangerous content</div>
          <div id="warning-comments" class="overlay-warnings"></div>
          <div class="overlay-buttons">
            <button id="btn-proceed" class="btn-proceed">Watch Anyway</button>
            <button id="btn-leave" class="btn-leave">Leave Video</button>
          </div>
        </div>
        
        <!-- Right side: Safe Alternatives -->
        <div id="alternatives-section">
          <div style="font-size: 20px; font-weight: 700; color: #4CAF50; margin-bottom: 15px; display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 28px;">✅</span>
            <span id="alternatives-title">Watch These Instead</span>
          </div>
          <div id="alternatives-message" style="font-size: 13px; color: #aaa; margin-bottom: 15px;">Safe, professional alternatives:</div>
          <div id="alternatives-list" style="display: flex; flex-direction: column; gap: 12px;"></div>
        </div>
        
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  // Button handlers
  const btnProceed = document.getElementById('btn-proceed');
  if (btnProceed) {
    btnProceed.onclick = () => {
      try {
        overlay.style.display = 'none';
      } catch (e) { console.error(e); }
    };
  }

  const btnLeave = document.getElementById('btn-leave');
  if (btnLeave) {
    btnLeave.onclick = () => {
      try {
        window.history.back();
      } catch (e) { console.error(e); }
    };
  }

}

/** Inject the YouTube-styled AI content banner with tabbed alternatives. */
function injectAIBanner() {
  // Remove existing if any
  const existing = document.getElementById('ai-content-banner');
  if (existing) existing.remove();

  // Create YouTube-styled AI content panel - LARGER with tabs
  const banner = document.createElement('div');
  banner.id = 'ai-content-banner';
  // Styles in content.css

  banner.innerHTML = `
    <div class="yt-header">
      <div class="yt-header-left">
        <div class="yt-ai-icon">🤖</div>
        <div class="yt-header-text">
          <h2>AI-Generated Content Detected</h2>
          <p id="ai-banner-message">This video appears to contain AI-generated content</p>
        </div>
      </div>
      <button class="yt-close-btn" id="ai-banner-close">✕</button>
    </div>
    
    <div class="yt-tabs" id="ai-tabs">
      <button class="yt-tab active" data-tab="real">
        <span class="yt-tab-icon">🎬</span>Watch Real Videos
      </button>
      <button class="yt-tab" data-tab="tutorials">
        <span class="yt-tab-icon">🎓</span>Learn to Make AI Videos
      </button>
      <button class="yt-tab" data-tab="entertainment">
        <span class="yt-tab-icon">🎨</span>More AI Content
      </button>
    </div>
    
    <div class="yt-tab-content active" id="tab-real">
      <div class="yt-grid" id="grid-real">
        <div class="yt-loading">
          <div class="yt-spinner"></div>
          <span>Finding real videos...</span>
        </div>
      </div>
    </div>
    
    <div class="yt-tab-content" id="tab-tutorials">
      <div class="yt-grid" id="grid-tutorials">
        <div class="yt-loading">
          <div class="yt-spinner"></div>
          <span>Loading AI tutorials...</span>
        </div>
      </div>
    </div>
    
    <div class="yt-tab-content" id="tab-entertainment">
      <div class="yt-grid" id="grid-entertainment">
        <div class="yt-loading">
          <div class="yt-spinner"></div>
          <span>Finding AI entertainment...</span>
        </div>
      </div>
    </div>
    
    <div class="yt-footer">
      <div class="yt-footer-left">
        <span style="color: #717171; font-size: 12px;">Format:</span>
        <div class="yt-format-toggle">
          <button class="yt-format-btn active" id="ai-format-long">📺 Videos</button>
          <button class="yt-format-btn" id="ai-format-shorts">⚡ Shorts</button>
        </div>
      </div>
      <div class="yt-footer-right">
        <button class="yt-btn yt-btn-secondary" id="ai-watch-anyway">Watch Anyway</button>
      </div>
    </div>
  `;

  document.body.appendChild(banner);

  // Store detected subject for API calls
  banner.dataset.detectedSubject = '';
  banner.dataset.preferShorts = 'false';
  banner.dataset.loadedTabs = '';

  document.getElementById('ai-banner-close').onclick = () => {
    try {
      banner.style.display = 'none';
    } catch (e) {
      console.error(e);
    }
  };

  document.getElementById('ai-watch-anyway').onclick = () => {
    try {
      banner.style.display = 'none';
    } catch (e) {
      console.error(e);
    }
  };

  // Tab switching
  const tabs = banner.querySelectorAll('.yt-tab');
  tabs.forEach(tab => {
    tab.onclick = () => {
      try {
        const tabName = tab.dataset.tab;

        // Update active tab
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        // Show tab content
        banner.querySelectorAll('.yt-tab-content').forEach(c => c.classList.remove('active'));
        const targetContent = document.getElementById(`tab-${tabName}`);
        if (targetContent) targetContent.classList.add('active');

        // Load content if not already loaded
        if (typeof loadTabContent === 'function') {
          loadTabContent(tabName);
        } else {
          console.error('loadTabContent function not found');
        }
      } catch (e) {
        console.error('Error switching tabs:', e);
      }
    };
  });

  // Format toggle handlers
  const longBtn = document.getElementById('ai-format-long');
  const shortsBtn = document.getElementById('ai-format-shorts');

  if (longBtn) {
    longBtn.onclick = () => {
      try {
        longBtn.classList.add('active');
        if (shortsBtn) shortsBtn.classList.remove('active');
        banner.dataset.preferShorts = 'false';
        // Reload current tab
        if (typeof reloadCurrentTab === 'function') {
          reloadCurrentTab();
        }
      } catch (e) { console.error(e); }
    };
  }

  if (shortsBtn) {
    shortsBtn.onclick = () => {
      try {
        if (shortsBtn) shortsBtn.classList.add('active');
        if (longBtn) longBtn.classList.remove('active');
        banner.dataset.preferShorts = 'true';
        // Reload current tab
        if (typeof reloadCurrentTab === 'function') {
          reloadCurrentTab();
        }
      } catch (e) { console.error(e); }
    };
  }

}

/**
 * Reload the currently active AI banner tab when format (Videos/Shorts) is toggled.
 * Clears loaded state so loadTabContent will re-fetch with new format preference.
 */
function reloadCurrentTab() {
  const banner = document.getElementById('ai-content-banner');
  if (!banner) return;
  const activeTab = banner.querySelector('.yt-tab.active');
  if (!activeTab) return;
  const tabName = activeTab.dataset.tab;
  // Clear loaded flag for this tab so it reloads
  const loaded = (banner.dataset.loadedTabs || '').split(',').filter(t => t && t !== tabName);
  banner.dataset.loadedTabs = loaded.join(',');
  if (typeof loadTabContent === 'function') {
    loadTabContent(tabName, true);
  }
}

/**
 * Create an XSS-safe video card element for alternative suggestions.
 * @param {Object} video - Video data (title, channel, thumbnail, url, badge)
 * @param {string} [type='real'] - Card type: 'real', 'tutorials', or 'entertainment'
 * @returns {string} Sanitized HTML string
 */
function createVideoCard(video, type = 'real') {
  const badgeClass = type === 'tutorials' ? 'tutorial' : type === 'entertainment' ? 'ai' : (video.is_trusted ? 'trusted' : '');
  const badgeText = video.badge || (type === 'tutorials' ? '🎓 Tutorial' : type === 'entertainment' ? '🤖 AI' : '✓ Real');

  // Sanitize URL to prevent XSS (only allow YouTube URLs)
  const safeUrl = video.url && (video.url.startsWith('https://www.youtube.com/') || video.url.startsWith('https://youtube.com/'))
    ? escapeHtml(video.url)
    : '#';

  return `
    <div class="yt-video-card" data-href="${safeUrl}">
      <div class="yt-thumb-container">
        <img class="yt-thumb" src="${escapeHtml(video.thumbnail || '')}" alt="" loading="lazy"
             data-fallback="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 320 180%22><rect fill=%22%23272727%22 width=%22320%22 height=%22180%22/><text x=%2250%25%22 y=%2250%25%22 fill=%22%23717171%22 font-size=%2224%22 text-anchor=%22middle%22 dy=%22.3em%22>🎬</text></svg>">
        <div class="yt-thumb-overlay">
          <div class="yt-play-icon"></div>
        </div>
        <span class="yt-badge ${badgeClass}">${escapeHtml(badgeText)}</span>
      </div>
      <div class="yt-video-info">
        <div class="yt-video-title">${escapeHtml(video.title || 'Untitled')}</div>
        <div class="yt-channel-name">${escapeHtml(video.channel || 'Unknown')}</div>
      </div>
    </div>
  `;
}

/**
 * Show the AI content banner with a message and load alternative tabs.
 * @param {string} message - Banner message text
 * @param {number} [duration=0] - Auto-hide delay in ms (0 = don't auto-hide)
 * @param {Array} [alternatives=[]] - Pre-fetched alternative videos
 * @param {string|null} [detectedAnimal=null] - Detected animal subject for targeted search
 */
function showAIBanner(message, duration = 0, alternatives = [], detectedAnimal = null) {
  const banner = document.getElementById('ai-content-banner');
  const messageEl = document.getElementById('ai-banner-message');

  if (!banner || !messageEl) return;

  messageEl.textContent = message || 'This video appears to contain AI-generated content';

  // Store detected subject for API calls
  if (detectedAnimal) {
    banner.dataset.detectedSubject = detectedAnimal;
  }

  // Reset loaded tabs for fresh content
  banner.dataset.loadedTabs = '';

  // Add YouTube API attribution
  addYouTubeAttribution(banner);

  // Show the banner
  banner.style.display = 'block';

  // Attach delegated click/error handlers for video cards and thumbnails
  attachCardHandlers(banner);

  // Immediately load all tabs content (don't wait for alternatives to be passed in)
  if (typeof loadTabContent === 'function') {
    loadTabContent('real', true);
    loadTabContent('tutorials', true);
    loadTabContent('entertainment', true);
  }

  // Auto-hide after duration (0 = don't auto-hide)
  if (duration > 0) {
    setTimeout(() => {
      banner.style.display = 'none';
    }, duration);
  }
}

/**
 * Attach delegated click/error handlers for video cards — CSP-safe replacement
 * for inline onclick and onerror attributes.
 * @param {HTMLElement} container - Parent container to attach handlers to
 */
function attachCardHandlers(container) {
  // Prevent duplicate listeners by marking the container
  if (container._ysiHandlersAttached) return;
  container._ysiHandlersAttached = true;

  // Delegated click handler for video cards (replaces inline onclick)
  container.addEventListener('click', (e) => {
    const card = e.target.closest('.yt-video-card[data-href]');
    if (card && card.dataset.href && card.dataset.href !== '#') {
      const href = card.dataset.href;
      // Only allow navigation to exact YouTube watch/shorts URLs
      if (/^https:\/\/(www\.)?youtube\.com\/(watch\?v=[a-zA-Z0-9_-]{11}|shorts\/[a-zA-Z0-9_-]{11})/.test(href)) {
        window.location.href = href;
      }
    }
  });

  // Delegated error handler for thumbnail images (works for dynamically loaded images too)
  container.addEventListener('error', (e) => {
    if (e.target.matches && e.target.matches('img.yt-thumb[data-fallback]')) {
      e.target.src = e.target.dataset.fallback;
      delete e.target.dataset.fallback; // Prevent infinite loop
    }
  }, true); // useCapture: true — error events don't bubble, but they do propagate in capture phase
}

/**
 * Show a brief slide-in flash notification for AI content.
 * @param {number} [duration=1500] - How long to show the flash in ms
 */
function showQuickAIFlash(duration = 1500) {
  // Create a brief flash overlay for AI content reminder
  let flash = document.getElementById('ai-flash-overlay');

  if (!flash) {
    flash = document.createElement('div');
    flash.id = 'ai-flash-overlay';
    // Usage of id selector for css in content.css

    flash.innerHTML = `
      <div style="display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 24px;">🤖</span>
        <span style="font-size: 14px; font-weight: 700; color: #fff;">AI CONTENT</span>
      </div>
    `;

    document.body.appendChild(flash);
  }

  // Show flash
  flash.style.display = 'block';
  flash.style.animation = 'flash-slide-in 0.3s ease-out';

  // Hide after duration with slide-out animation
  setTimeout(() => {
    flash.style.animation = 'flash-slide-out 0.3s ease-out';
    setTimeout(() => {
      flash.style.display = 'none';
    }, 300);
  }, duration);
}
