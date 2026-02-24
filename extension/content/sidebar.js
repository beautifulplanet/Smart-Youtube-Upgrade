/**
 * YouTube Safety Inspector - Sidebar Component (v4 — Analysis Hub)
 * Copyright (c) 2026 beautifulplanet
 * Licensed under MIT License
 *
 * Two-state sidebar:
 *   CHILL  — green badge + scrollable thumbnail grid (no issues)
 *   ALERT  — score, flags, warnings + alternatives below
 *
 * Uses Shadow DOM for complete CSS isolation from YouTube.
 * Dependencies: modes.js (readBridgeVideos, waitForBridge), utils.js
 */

/* global readBridgeVideos, waitForBridge, escapeHtml, getVideoId */

// ═══════════════════════════════════════════════
// Sidebar State
// ═══════════════════════════════════════════════

const SIDEBAR_STATE = {
  isVisible: false,
  isCollapsed: false,
  sidebarEl: null,
  shadowRoot: null,
  styleEl: null,
  currentResults: null,
  mode: 'chill',
};

// ═══════════════════════════════════════════════
// CSS Loader
// ═══════════════════════════════════════════════

let _sidebarCSSCache = null;

async function loadSidebarCSS() {
  if (_sidebarCSSCache) return _sidebarCSSCache;
  try {
    const url = chrome.runtime.getURL('content/sidebar.css');
    const response = await fetch(url);
    _sidebarCSSCache = await response.text();
  } catch (e) {
    console.error('🛡️ Failed to load sidebar CSS:', e);
    _sidebarCSSCache = '/* CSS load failed */';
  }
  return _sidebarCSSCache;
}

// ═══════════════════════════════════════════════
// Sidebar DOM Construction
// ═══════════════════════════════════════════════

async function createSidebar() {
  if (document.getElementById('ysi-sidebar-host')) {
    const existing = document.getElementById('ysi-sidebar-host');
    SIDEBAR_STATE.sidebarEl = existing;
    // With closed shadow DOM, existing.shadowRoot is null.
    // If we already have the reference from initial creation, keep it.
    if (!SIDEBAR_STATE.shadowRoot) {
      // Re-create the sidebar if shadow reference was lost (e.g. page navigation)
      existing.remove();
    } else {
      return;
    }
  }

  const sidebarEl = document.createElement('div');
  sidebarEl.id = 'ysi-sidebar-host';
  // Explicit inline styles prevent YouTube CSS from hiding/breaking the host element
  sidebarEl.style.cssText = 'position:fixed!important;top:0!important;right:0!important;z-index:2147483647!important;width:0!important;height:0!important;overflow:visible!important;pointer-events:none!important;';

  // Security: closed shadow DOM prevents page scripts from accessing extension UI
  const shadow = sidebarEl.attachShadow({ mode: 'closed' });

  const css = await loadSidebarCSS();
  const styleTag = document.createElement('style');
  styleTag.textContent = css;
  shadow.appendChild(styleTag);

  const sidebar = document.createElement('div');
  sidebar.className = 'ysi-sidebar hidden';
  sidebar.innerHTML = buildSidebarHTML();
  shadow.appendChild(sidebar);

  document.body.appendChild(sidebarEl);

  SIDEBAR_STATE.sidebarEl = sidebarEl;
  SIDEBAR_STATE.shadowRoot = shadow;

  setupSidebarEvents(shadow);
  await loadSidebarState();

  console.log('🛡️ Sidebar created (Analysis Hub)');
}

function buildSidebarHTML() {
  return `
    <!-- Header -->
    <div class="ysi-header">
      <button class="ysi-icon-btn ysi-toggle-btn" title="Collapse sidebar" aria-label="Toggle sidebar">
        <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
      </button>
      <div class="ysi-header-brand">
        <span class="ysi-header-icon">🛡️</span>
        <span class="ysi-header-title">Safety Inspector</span>
      </div>
    </div>

    <!-- Analyzing State (shown while waiting for backend) -->
    <div class="ysi-state ysi-state-analyzing active" id="ysi-analyzing">
      <div class="ysi-chill-badge">
        <div class="ysi-chill-icon ysi-spin">🔍</div>
        <div class="ysi-chill-text">Analyzing...</div>
        <div class="ysi-chill-sub">Checking video safety</div>
      </div>
    </div>

    <!-- Error State (backend unreachable) -->
    <div class="ysi-state ysi-state-error" id="ysi-error">
      <div class="ysi-chill-badge">
        <div class="ysi-chill-icon">❌</div>
        <div class="ysi-chill-text" id="ysi-error-text">Backend Offline</div>
        <div class="ysi-chill-sub" id="ysi-error-sub">Start the backend server on localhost:8000</div>
      </div>
    </div>

    <!-- Ad Playing State (pause analysis display during ads) -->
    <div class="ysi-state ysi-state-ad" id="ysi-ad">
      <div class="ysi-chill-badge">
        <div class="ysi-chill-icon">📺</div>
        <div class="ysi-chill-text">Enjoy the Ad!</div>
        <div class="ysi-chill-sub">We only analyze the actual video — not ads.<br>Analysis will start automatically when it ends.</div>
      </div>
    </div>

    <!-- Chill State (safe — shown after analysis completes clean) -->
    <div class="ysi-state ysi-state-chill" id="ysi-chill">
      <div class="ysi-chill-badge">
        <div class="ysi-chill-icon">✅</div>
        <div class="ysi-chill-text">Looks Good</div>
        <div class="ysi-chill-sub">No safety issues detected</div>
        <a class="ysi-wiki-link" id="ysi-wiki-link" href="#" target="_blank" rel="noopener noreferrer">
          📖 Learn more on Wikipedia
        </a>
      </div>
      <div class="ysi-section-label">
        <span>Related Videos</span>
      </div>
      <div class="ysi-thumb-grid" id="ysi-chill-grid">
        <div class="ysi-loading">
          <div class="ysi-spinner"></div>
          <span>Loading...</span>
        </div>
      </div>
    </div>

    <!-- Alert State (issues found) -->
    <div class="ysi-state ysi-state-alert" id="ysi-alert">
      <!-- Score -->
      <div class="ysi-alert-score-row">
        <div class="ysi-score-ring" id="ysi-score-ring">
          <svg viewBox="0 0 60 60">
            <circle class="ysi-score-bg" cx="30" cy="30" r="26" />
            <circle class="ysi-score-fg" cx="30" cy="30" r="26" id="ysi-score-arc" />
          </svg>
          <span class="ysi-score-value" id="ysi-score-value">--</span>
        </div>
        <div class="ysi-score-info">
          <div class="ysi-score-label" id="ysi-score-label">Analyzing...</div>
          <div class="ysi-score-sub" id="ysi-score-sub"></div>
        </div>
      </div>

      <!-- Flags (top 5 relevant categories) -->
      <div class="ysi-flags" id="ysi-flags"></div>

      <!-- Warnings -->
      <div class="ysi-warnings" id="ysi-warnings"></div>

      <!-- Alternatives -->
      <div class="ysi-section-label" id="ysi-alt-label">
        <span>✅ Safe Alternatives</span>
      </div>
      <div class="ysi-thumb-grid" id="ysi-alert-grid"></div>
    </div>

    <!-- Collapsed Strip -->
    <div class="ysi-collapsed-strip">
      <div class="ysi-strip-icon-btn" title="Safety Inspector">🛡️</div>
    </div>
  `;
}

// ═══════════════════════════════════════════════
// Event Handling
// ═══════════════════════════════════════════════

function setupSidebarEvents(shadow) {
  const toggleBtn = shadow.querySelector('.ysi-toggle-btn');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', toggleSidebarCollapse);
  }

  // Delegated click for thumbnail cards — strict YouTube URL validation
  shadow.addEventListener('click', (e) => {
    const card = e.target.closest('.ysi-thumb-card[data-href]');
    if (card && card.dataset.href && card.dataset.href !== '#') {
      const href = card.dataset.href;
      // Only allow navigation to exact YouTube watch/shorts URLs
      if (/^https:\/\/(www\.)?youtube\.com\/(watch\?v=[a-zA-Z0-9_-]{11}|shorts\/[a-zA-Z0-9_-]{11})/.test(href)) {
        window.location.href = href;
      } else {
        console.warn('🛡️ Blocked navigation to non-YouTube URL:', href);
      }
    }
  });

  // Thumbnail image error fallback
  shadow.addEventListener('error', (e) => {
    if (e.target.matches && e.target.matches('img.ysi-thumb-img')) {
      e.target.src = 'data:image/svg+xml,' + encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180"><rect fill="#272727" width="320" height="180"/><text x="50%" y="50%" fill="#717171" font-size="24" text-anchor="middle" dy=".3em">🎬</text></svg>'
      );
    }
  }, true);
}

// ═══════════════════════════════════════════════
// State Switching
// ═══════════════════════════════════════════════

/**
 * Switch sidebar between chill and alert.
 * @param {'chill'|'alert'} mode
 */
function setSidebarMode(mode) {
  if (!SIDEBAR_STATE.shadowRoot) return;
  SIDEBAR_STATE.mode = mode;
  console.log('🛡️ Sidebar mode →', mode);

  const analyzing = SIDEBAR_STATE.shadowRoot.getElementById('ysi-analyzing');
  const error = SIDEBAR_STATE.shadowRoot.getElementById('ysi-error');
  const ad = SIDEBAR_STATE.shadowRoot.getElementById('ysi-ad');
  const chill = SIDEBAR_STATE.shadowRoot.getElementById('ysi-chill');
  const alert = SIDEBAR_STATE.shadowRoot.getElementById('ysi-alert');

  if (analyzing) analyzing.classList.toggle('active', mode === 'analyzing');
  if (error) error.classList.toggle('active', mode === 'error');
  if (ad) ad.classList.toggle('active', mode === 'ad');
  if (chill) chill.classList.toggle('active', mode === 'chill');
  if (alert) alert.classList.toggle('active', mode === 'alert');
}

/**
 * Show an error in the sidebar (e.g. backend offline).
 * @param {string} title - Error title
 * @param {string} sub - Error subtitle
 */
function showSidebarError(title, sub) {
  if (!SIDEBAR_STATE.shadowRoot) return;
  const textEl = SIDEBAR_STATE.shadowRoot.getElementById('ysi-error-text');
  const subEl = SIDEBAR_STATE.shadowRoot.getElementById('ysi-error-sub');
  if (textEl) textEl.textContent = title || 'Error';
  if (subEl) subEl.textContent = sub || '';
  setSidebarMode('error');
}

// ═══════════════════════════════════════════════
// Populate Analysis Results
// ═══════════════════════════════════════════════

/**
 * Called by analysis.js when results arrive.
 * @param {Object} results - Backend analysis results
 * @param {Object} settings - User settings (enableAIDetection, etc.)
 */
function updateSidebarWithResults(results, settings = {}) {
  if (!SIDEBAR_STATE.shadowRoot) return;
  SIDEBAR_STATE.currentResults = results;

  const aiFlag = settings.enableAIDetection !== false && results.ai_generated;

  // Store for use in populateAlertState
  SIDEBAR_STATE._aiFlag = aiFlag;

  const hasIssues = results.safety_score < 75 ||
    (results.warnings && results.warnings.some(w => w.severity === 'high' || w.severity === 'medium')) ||
    aiFlag;

  if (hasIssues) {
    setSidebarMode('alert');
    populateAlertState(results);
    
    // Update alternatives section label based on content type
    const altLabel = SIDEBAR_STATE.shadowRoot.getElementById('ysi-alt-label');
    if (altLabel) {
      if (results.is_debunking) {
        altLabel.textContent = '🔬 Debunking Videos';
      } else {
        altLabel.textContent = '✅ Safe Alternatives';
      }
    }
  } else {
    setSidebarMode('chill');
    populateWikiLink();
  }

  loadThumbnailGrid(results);
}

/**
 * Populate the Wikipedia link in the chill state.
 * Builds a Wikipedia search URL from the video title,
 * stripping common YouTube noise (episode numbers, "Official Video", etc.)
 */
function populateWikiLink() {
  const shadow = SIDEBAR_STATE.shadowRoot;
  if (!shadow) return;

  const link = shadow.getElementById('ysi-wiki-link');
  if (!link) return;

  const rawTitle = typeof getVideoTitle === 'function' ? getVideoTitle() : '';
  if (!rawTitle) {
    link.style.display = 'none';
    return;
  }

  // Strip common YouTube title noise for a cleaner Wikipedia search
  const cleaned = rawTitle
    .replace(/\s*[\|\-–—]\s*(official\s*(video|audio|music\s*video|lyric\s*video)|lyric\s*video|full\s*episode|hd|hq|4k|remastered|lyrics?)\s*/gi, '')
    .replace(/\(official\s*(video|audio|music\s*video|lyric\s*video)\)/gi, '')
    .replace(/\[official\s*(video|audio|music\s*video|lyric\s*video)\]/gi, '')
    .replace(/\s*\(?(ep\.?\s*\d+|episode\s*\d+|s\d+\s*e\d+|season\s*\d+)\)?\s*/gi, '')
    .replace(/\s*#\w+/g, '')        // hashtags
    .replace(/\s*\|\s*[^|]*$/g, '') // trailing pipe segments (channel names)
    .replace(/\s{2,}/g, ' ')        // collapse whitespace
    .trim();

  if (!cleaned) {
    link.style.display = 'none';
    return;
  }

  const wikiUrl = `https://en.wikipedia.org/w/index.php?search=${encodeURIComponent(cleaned)}`;
  link.href = wikiUrl;
  link.title = `Search Wikipedia for "${cleaned}"`;
  link.style.display = '';
}

/**
 * Populate alert state with score, flags, warnings.
 */
function populateAlertState(results) {
  const shadow = SIDEBAR_STATE.shadowRoot;
  if (!shadow) return;

  // --- Score ring ---
  const scoreValue = shadow.getElementById('ysi-score-value');
  const scoreLabel = shadow.getElementById('ysi-score-label');
  const scoreSub = shadow.getElementById('ysi-score-sub');
  const scoreArc = shadow.getElementById('ysi-score-arc');

  const score = results.safety_score ?? 0;

  if (scoreValue) scoreValue.textContent = score;
  if (scoreLabel) {
    if (score < 25) scoreLabel.textContent = 'Dangerous';
    else if (score < 50) scoreLabel.textContent = 'Unsafe';
    else if (score < 75) scoreLabel.textContent = 'Caution';
    else scoreLabel.textContent = 'Mostly Safe';
  }
  if (scoreSub) {
    const warnCount = (results.warnings || []).length;
    scoreSub.textContent = warnCount > 0 ? `${warnCount} warning${warnCount > 1 ? 's' : ''} found` : '';
  }

  // Animate the ring arc
  if (scoreArc) {
    const circumference = 2 * Math.PI * 26; // r=26
    const offset = circumference - (score / 100) * circumference;
    scoreArc.style.strokeDasharray = `${circumference}`;
    scoreArc.style.strokeDashoffset = `${offset}`;

    if (score < 25) scoreArc.style.stroke = 'var(--danger)';
    else if (score < 50) scoreArc.style.stroke = 'var(--warning)';
    else if (score < 75) scoreArc.style.stroke = '#f0c020';
    else scoreArc.style.stroke = 'var(--success)';
  }

  // --- Flags (only categories with issues — hide safe/100-score ones) ---
  const flagsEl = shadow.getElementById('ysi-flags');
  if (flagsEl) {
    const categories = results.categories || {};
    const problemCategories = Object.entries(categories)
      .filter(([, data]) => (data.score ?? 100) < 100)  // Only show categories with issues
      .sort((a, b) => a[1].score - b[1].score)
      .slice(0, 5);

    if (problemCategories.length > 0) {
      flagsEl.innerHTML = problemCategories.map(([name, data]) => {
        const catScore = data.score ?? 100;
        let icon, cls;
        if (catScore < 50) { icon = '🔴'; cls = 'danger'; }
        else if (catScore < 80) { icon = '⚠️'; cls = 'caution'; }
        else { icon = '⚡'; cls = 'caution'; }

        const label = name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        return `
          <div class="ysi-flag ${cls}">
            <span class="ysi-flag-icon">${icon}</span>
            <span class="ysi-flag-label">${escapeHtml(label)}</span>
            <span class="ysi-flag-score">${escapeHtml(String(catScore))}</span>
          </div>
        `;
      }).join('');
    } else {
      flagsEl.innerHTML = '';
    }
  }

  // --- Warnings ---
  const warningsEl = shadow.getElementById('ysi-warnings');
  if (warningsEl) {
    const warnings = results.warnings || [];
    const severe = warnings.filter(w => w.severity === 'high' || w.severity === 'medium');

    if (severe.length > 0) {
      warningsEl.innerHTML = severe.map(w => {
        const color = w.severity === 'high' ? 'var(--danger)' : 'var(--warning)';
        const icon = w.severity === 'high' ? '⚠️' : '⚡';
        
        // Build evidence section if available
        let evidenceHtml = '';
        if (w.evidence && w.evidence.length > 0) {
          const evidenceRows = w.evidence.map(e => {
            // Pick tag color based on evidence type
            let tagCls = 'ysi-ev-other';
            if (e.type === 'channel') tagCls = 'ysi-ev-channel';
            else if (e.type === 'title') tagCls = 'ysi-ev-title';
            else if (e.type === 'description') tagCls = 'ysi-ev-desc';
            else if (e.type === 'co_occurrence') tagCls = 'ysi-ev-cooccur';
            else if (e.type === 'hashtag') tagCls = 'ysi-ev-hashtag';
            
            return `
              <div class="ysi-evidence-row">
                <span class="ysi-evidence-label">${escapeHtml(e.label)}</span>
                <span class="ysi-evidence-tag ${tagCls}">${escapeHtml(e.value)}</span>
              </div>
            `;
          }).join('');
          
          evidenceHtml = `
            <div class="ysi-evidence-section">
              <div class="ysi-evidence-header">🔍 Evidence Found</div>
              ${evidenceRows}
            </div>
          `;
        }

        return `
          <div class="ysi-warning-card" style="border-left-color: ${color};">
            <div class="ysi-warning-title">
              <span>${icon}</span>
              ${escapeHtml(w.category || 'Warning')}
            </div>
            <div class="ysi-warning-msg">${escapeHtml(w.message || '')}</div>
            ${evidenceHtml}
          </div>
        `;
      }).join('');
    } else if (SIDEBAR_STATE._aiFlag) {
      const confidence = results.ai_confidence ? Math.round(results.ai_confidence * 100) : 0;
      warningsEl.innerHTML = `
        <div class="ysi-warning-card" style="border-left-color: var(--blue);">
          <div class="ysi-warning-title">
            <span>🤖</span> AI Content Detected
          </div>
          <div class="ysi-warning-msg">This video appears to contain AI-generated content (${confidence}% confidence).</div>
        </div>
      `;
    } else {
      warningsEl.innerHTML = '';
    }
  }
}

// ═══════════════════════════════════════════════
// Thumbnail Grid
// ═══════════════════════════════════════════════

/**
 * Load thumbnails into the active grid.
 */
async function loadThumbnailGrid(results) {
  const shadow = SIDEBAR_STATE.shadowRoot;
  if (!shadow) return;

  const gridId = SIDEBAR_STATE.mode === 'alert' ? 'ysi-alert-grid' : 'ysi-chill-grid';
  const grid = shadow.getElementById(gridId);
  if (!grid) return;

  // Try backend alternatives first
  let videos = [];
  if (results && results.alternatives && results.alternatives.length > 0) {
    videos = results.alternatives.slice(0, 12);
  }

  // Fall back to bridge videos (YouTube related sidebar)
  if (videos.length < 6) {
    try {
      if (typeof waitForBridge === 'function') await waitForBridge(8000);
      if (typeof readBridgeVideos === 'function') {
        const bridgeVideos = readBridgeVideos(16);
        const currentId = typeof getVideoId === 'function' ? getVideoId() : null;
        const existingIds = new Set(videos.map(v => v.video_id || v.videoId));
        const extra = bridgeVideos
          .filter(v => v.videoId !== currentId && !existingIds.has(v.videoId))
          .slice(0, 12 - videos.length)
          .map(v => ({
            title: v.title,
            channel: v.channel,
            thumbnail: v.thumbnail,
            url: `https://www.youtube.com/watch?v=${v.videoId}`,
          }));
        videos = videos.concat(extra);
      }
    } catch (e) {
      console.warn('🛡️ Bridge fetch failed:', e);
    }
  }

  if (videos.length === 0) {
    grid.innerHTML = `
      <div class="ysi-empty">
        <div class="ysi-empty-icon">🎬</div>
        <div>No videos available yet</div>
      </div>
    `;
    return;
  }

  grid.innerHTML = videos.slice(0, 12).map(v => {
    const safeUrl = (v.url || '').startsWith('https://www.youtube.com/') || (v.url || '').startsWith('https://youtube.com/')
      ? escapeHtml(v.url)
      : '#';
    const thumb = v.thumbnail || `https://i.ytimg.com/vi/${v.videoId || v.video_id || ''}/mqdefault.jpg`;
    return `
      <div class="ysi-thumb-card" data-href="${safeUrl}">
        <div class="ysi-thumb-wrap">
          <img class="ysi-thumb-img" src="${escapeHtml(thumb)}" alt="" loading="lazy">
          <div class="ysi-thumb-hover">
            <div class="ysi-play-icon"></div>
          </div>
        </div>
        <div class="ysi-thumb-info">
          <div class="ysi-thumb-title">${escapeHtml(v.title || 'Untitled')}</div>
          <div class="ysi-thumb-channel">${escapeHtml(v.channel || '')}</div>
        </div>
      </div>
    `;
  }).join('');
}

/**
 * Load chill grid on navigation (before analysis results arrive).
 */
async function loadChillGrid() {
  if (!SIDEBAR_STATE.shadowRoot) return;
  setSidebarMode('chill');
  await loadThumbnailGrid({});
}

// ═══════════════════════════════════════════════
// Sidebar Visibility & Collapse
// ═══════════════════════════════════════════════

function showSidebar() {
  if (!SIDEBAR_STATE.shadowRoot) return;
  const sidebar = SIDEBAR_STATE.shadowRoot.querySelector('.ysi-sidebar');
  if (!sidebar) return;

  sidebar.classList.remove('hidden');
  SIDEBAR_STATE.isVisible = true;

  if (SIDEBAR_STATE.isCollapsed) {
    sidebar.classList.add('collapsed');
  }

  applyYouTubeLayoutAdjustment(true);
}

function hideSidebar() {
  if (!SIDEBAR_STATE.shadowRoot) return;
  const sidebar = SIDEBAR_STATE.shadowRoot.querySelector('.ysi-sidebar');
  if (!sidebar) return;

  sidebar.classList.add('hidden');
  SIDEBAR_STATE.isVisible = false;
  applyYouTubeLayoutAdjustment(false);
}

function toggleSidebarCollapse() {
  if (!SIDEBAR_STATE.shadowRoot) return;
  const sidebar = SIDEBAR_STATE.shadowRoot.querySelector('.ysi-sidebar');
  if (!sidebar) return;

  SIDEBAR_STATE.isCollapsed = !SIDEBAR_STATE.isCollapsed;
  sidebar.classList.toggle('collapsed', SIDEBAR_STATE.isCollapsed);

  const toggleBtn = SIDEBAR_STATE.shadowRoot.querySelector('.ysi-toggle-btn');
  if (toggleBtn) {
    toggleBtn.innerHTML = SIDEBAR_STATE.isCollapsed
      ? '<svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>'
      : '<svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>';
    toggleBtn.title = SIDEBAR_STATE.isCollapsed ? 'Expand sidebar' : 'Collapse sidebar';
  }

  applyYouTubeLayoutAdjustment(SIDEBAR_STATE.isVisible);
  saveSidebarState();
}

// ═══════════════════════════════════════════════
// YouTube Layout Adjustment
// ═══════════════════════════════════════════════

function applyYouTubeLayoutAdjustment(sidebarOpen) {
  if (SIDEBAR_STATE.styleEl) {
    SIDEBAR_STATE.styleEl.remove();
    SIDEBAR_STATE.styleEl = null;
  }

  if (!sidebarOpen) return;

  const width = SIDEBAR_STATE.isCollapsed ? '48px' : '380px';

  const style = document.createElement('style');
  style.id = 'ysi-layout-adjust';
  style.textContent = `
    ytd-app { margin-right: ${width} !important; }
    #masthead-container, ytd-masthead { width: calc(100% - ${width}) !important; }
    ytd-watch-flexy { max-width: 100% !important; }
    ytd-browse, ytd-search { max-width: 100% !important; }
    tp-yt-app-drawer { width: auto !important; }
  `;

  document.head.appendChild(style);
  SIDEBAR_STATE.styleEl = style;
}

// ═══════════════════════════════════════════════
// State Persistence
// ═══════════════════════════════════════════════

function saveSidebarState() {
  try {
    chrome.storage.local.set({ sidebarState: { isCollapsed: SIDEBAR_STATE.isCollapsed } });
  } catch (_e) { /* ignore */ }
}

async function loadSidebarState() {
  try {
    const result = await new Promise(resolve => {
      chrome.storage.local.get(['sidebarState'], resolve);
    });
    if (result.sidebarState) {
      SIDEBAR_STATE.isCollapsed = result.sidebarState.isCollapsed || false;
      if (SIDEBAR_STATE.isCollapsed) {
        const sidebar = SIDEBAR_STATE.shadowRoot?.querySelector('.ysi-sidebar');
        if (sidebar) sidebar.classList.add('collapsed');
      }
    }
  } catch (_e) { /* defaults */ }
}

// ═══════════════════════════════════════════════
// SPA Navigation
// ═══════════════════════════════════════════════

function onNavigationForSidebar(videoId) {
  if (videoId) {
    showSidebar();
    setSidebarMode('analyzing');
  } else {
    hideSidebar();
  }
}
