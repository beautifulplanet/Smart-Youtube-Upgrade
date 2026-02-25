/**
 * YouTube Safety Inspector - Analysis Logic
 * Copyright (c) 2026 beautifulplanet
 * Licensed under MIT License
 */

// State for analysis
let currentVideoId = null;
let lastAnalysisTime = 0;

/**
 * Check if the Chrome extension context is still valid.
 * Returns false when the content script has been orphaned by navigation/reload.
 */
function isExtensionContextValid() {
    try {
        return !!(chrome.runtime && chrome.runtime.id);
    } catch {
        return false;
    }
}

// Default settings (must match popup.js defaults)
const DEFAULT_SETTINGS = {
    enableAIDetection: true,
    autoAnalyze: true,
    enableRegularVideos: true,
    enableShorts: true,
    enableAlternatives: true
};

// Cached settings — updated via storage.onChanged listener to avoid
// reading chrome.storage.sync on every checkVideo() call (#16)
let _cachedSettings = null;

// Listen for settings changes from popup
chrome.storage.onChanged.addListener((changes, area) => {
    if (!isExtensionContextValid()) return;
    if (area === 'sync' && changes.inspectorSettings) {
        _cachedSettings = { ...DEFAULT_SETTINGS, ...changes.inspectorSettings.newValue };
    }
});

/**
 * W3.1: Get settings from storage with defaults
 * Uses cache when available to avoid repeated async I/O.
 * @returns {Promise<Object>} Settings object
 */
async function getSettings() {
    if (_cachedSettings) return _cachedSettings;
    if (!isExtensionContextValid()) return DEFAULT_SETTINGS;
    try {
        const result = await chrome.storage.sync.get('inspectorSettings');
        _cachedSettings = { ...DEFAULT_SETTINGS, ...result.inspectorSettings };
        return _cachedSettings;
    } catch (err) {
        console.warn('Failed to load settings, using defaults:', err);
        return DEFAULT_SETTINGS;
    }
}

/**
 * Main function to trigger video analysis
 * @param {string} videoId YouTube Video ID
 * @param {boolean} force Force re-analysis even if recently checked
 */
async function checkVideo(videoId, force = false) {
    try {
        if (!videoId) return;

        // Guard: bail if extension context was destroyed (SPA navigation orphaned this script)
        if (!isExtensionContextValid()) {
            console.log('🛡️ Extension context invalid — skipping analysis');
            return;
        }

        // --- AD-FIRST GATE ---
        // If a pre-roll ad is playing, show "Ad Playing" and defer analysis.
        // The ad-check interval (content.js) will call checkVideo() when the ad ends.
        if (typeof isAdPlaying === 'function' && isAdPlaying()) {
            console.log('🛡️ Ad playing — deferring analysis until ad finishes');
            currentVideoId = videoId; // remember which video to analyze later
            if (typeof hideAllOverlays === 'function') hideAllOverlays();
            if (typeof setSidebarMode === 'function') setSidebarMode('ad');
            return; // Exit — ad interval will re-call us
        }

        // Prevent duplicate checks
        if (videoId === currentVideoId && !force && (Date.now() - lastAnalysisTime < 30000)) {
            return;
        }

        // W3.2: Check Auto-Analyze setting
        const settings = await getSettings();
        if (!force && !settings.autoAnalyze) {
            console.log('🛡️ Auto-analyze disabled by user');
            return;
        }

        // Check video type settings
        const isShorts = location.pathname.includes('/shorts/');
        if (!isShorts && !settings.enableRegularVideos) {
            console.log('🛡️ Regular video analysis disabled by user');
            return;
        }
        if (isShorts && !settings.enableShorts) {
            console.log('🛡️ Shorts analysis disabled by user');
            return;
        }

        currentVideoId = videoId;

        lastAnalysisTime = Date.now();

        // Hide previous overlays
        if (typeof hideAllOverlays === 'function') hideAllOverlays();

        // Scrape metadata using utils
        // For Shorts, YouTube's DOM may not have updated yet — wait a beat
        let title = typeof getVideoTitle === 'function' ? getVideoTitle() : '';
        if (isShorts && (!title || title === document.title.replace(' - YouTube', '').trim())) {
            // DOM hasn't hydrated the new Short's title yet — wait and retry
            await new Promise(r => setTimeout(r, 800));
            title = typeof getVideoTitle === 'function' ? getVideoTitle() : '';
        }
        const channel = typeof getChannelName === 'function' ? getChannelName() : '';
        const description = typeof getVideoDescription === 'function' ? getVideoDescription() : '';

        // Send message to background script to handle API call
        console.log('🛡️ Sending ANALYZE_VIDEO for', videoId, '| title:', title, '| channel:', channel, '| force:', force);

        // Show analyzing state in sidebar
        if (typeof setSidebarMode === 'function') {
            setSidebarMode('analyzing');
        }

        // Guard again before async Chrome API call (context may have died during await)
        if (!isExtensionContextValid()) {
            console.log('🛡️ Extension context lost before sendMessage — aborting');
            return;
        }

        chrome.runtime.sendMessage({
            type: 'ANALYZE_VIDEO',
            videoId: videoId,
            title: title,
            channel: channel,
            description: description,
            force: force
        }, (response) => {
            if (chrome.runtime.lastError) {
                console.error('🛡️ Analysis error:', chrome.runtime.lastError);
                if (typeof showSidebarError === 'function') {
                    showSidebarError('Connection Error', chrome.runtime.lastError.message);
                }
                return;
            }

            console.log('🛡️ Analysis response:', JSON.stringify(response).substring(0, 300));

            if (response && response.success) {
                console.log('🛡️ Got results: score=' + response.data.safety_score +
                    ', ai=' + response.data.ai_generated +
                    ', warnings=' + (response.data.warnings || []).length);
                // W3.3: Pass settings to processing
                processAnalysisResults(response.data, settings);
            } else if (response && response.error) {
                console.error('🛡️ API Error:', response.error);
                if (typeof showSidebarError === 'function') {
                    showSidebarError('Analysis Failed', response.error);
                }
            } else {
                console.error('🛡️ No response from background script');
                if (typeof showSidebarError === 'function') {
                    showSidebarError('No Response', 'Background script did not respond');
                }
            }
        });
    } catch (err) {
        console.error('\ud83d\udee1\ufe0f Error in checkVideo:', err);

    }
}

/**
 * Process results from backend and update UI
 * @param {Object} results Analysis results JSON
 * @param {Object} settings User settings
 */
function processAnalysisResults(results, settings = DEFAULT_SETTINGS) {
    try {
        if (results.error) {
            console.error('🛡️ API Error:', results.error);
            return;
        }

        console.log('🛡️ Processing results: score=' + results.safety_score + ', ai=' + results.ai_generated);

        // Update sidebar with results (two-state: chill / alert)
        if (typeof updateSidebarWithResults === 'function') {
            updateSidebarWithResults(results, settings);
        } else {
            console.error('🛡️ updateSidebarWithResults not available!');
        }

        // 1. Safety Score Check (always on — safety guardrails are standard)
        // Threshold aligned with sidebar's alert state (<75) — overlay only for severe cases
        if (results.safety_score < 50 && results.warnings && results.warnings.length > 0) {
            const severeWarnings = results.warnings.filter(w => w.severity === 'high');

            if (severeWarnings.length > 0) {
                // Show overlay
                if (typeof injectOverlay === 'function') injectOverlay();

                const scoreEl = document.getElementById('safety-score');
                const commentsEl = document.getElementById('warning-comments');
                const overlay = document.getElementById('safety-overlay');

                if (scoreEl) {
                    scoreEl.textContent = results.safety_score;
                    scoreEl.setAttribute('role', 'meter');
                    scoreEl.setAttribute('aria-valuenow', results.safety_score);
                    scoreEl.setAttribute('aria-valuemin', '0');
                    scoreEl.setAttribute('aria-valuemax', '100');
                    scoreEl.setAttribute('aria-label', `Safety Score: ${results.safety_score} out of 100`);
                }

                if (commentsEl) {
                    commentsEl.setAttribute('role', 'alert');
                    commentsEl.innerHTML = severeWarnings.map(w =>
                        `<div class="ysi-warning-card" style="padding: 12px; background: rgba(255,68,68,0.1); border-left: 4px solid #ff4444; margin-bottom: 10px; border-radius: 4px;">
                            <div style="font-weight: 700; color: #ff4444; font-size: 14px; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">
                                <span aria-hidden="true">⚠️</span> ${escapeHtml(w.category)}
                            </div>
                            <div style="color: #eee; font-size: 13px; line-height: 1.4;">${escapeHtml(w.message)}</div>
                        </div>`
                    ).join('');
                }

                if (overlay) overlay.style.display = 'flex';

                // Auto-load alternatives for dangerous content (Gated by enableAlternatives)
                if (settings.enableAlternatives && results.alternatives && results.alternatives.length > 0) {
                    const altSection = document.getElementById('alternatives-section');
                    const altList = document.getElementById('alternatives-list');

                    if (altSection && altList) {
                        altSection.style.display = 'block';
                        altList.innerHTML = results.alternatives.map(video => createVideoCard(video)).join('');
                    }
                }
            }
        }

        // 2. AI Content Check (Gated by enableAIDetection)
        if (settings.enableAIDetection && results.ai_generated) {
            if (typeof injectAIBanner === 'function') injectAIBanner();

            const confidence = results.ai_confidence ? Math.round(results.ai_confidence * 100) : 0;
            const reasons = results.ai_reasons || [];
            const reasonText = reasons.length > 0 ? reasons[0] : 'AI patterns detected';

            // Show banner with AI info
            if (typeof showAIBanner === 'function') {
                showAIBanner(
                    `AI Content Detected (${confidence}% confidence): ${reasonText}`,
                    0, // Don't auto-hide
                    results.alternatives || [],
                    results.detected_animal // Pass detected animal for better recommendations
                );
            }
        }
    } catch (err) {
        console.error('\ud83d\udee1\ufe0f Error processing results:', err);
    }
}

/**
 * Load content for AI banner tabs
 * @param {string} tabName 'real', 'tutorials', or 'entertainment'
 * @param {boolean} forceReload Force fresh fetch
 */
async function loadTabContent(tabName, forceReload = false) {
    const banner = document.getElementById('ai-content-banner');
    if (!banner) return;

    // Check if already loaded
    const loadedTabs = (banner.dataset.loadedTabs || '').split(',');
    if (!forceReload && loadedTabs.includes(tabName)) return;

    const grid = document.getElementById(`grid-${tabName}`);
    if (!grid) return;

    // Show loading state
    grid.innerHTML = `
    <div class="yt-loading">
      <div class="yt-spinner"></div>
      <span>Finding best videos...</span>
    </div>
  `;

    // Get context from banner
    const detectedSubject = banner.dataset.detectedSubject || '';
    const preferShorts = banner.dataset.preferShorts === 'true';
    const videoId = typeof currentVideoId !== 'undefined' ? currentVideoId : '';

    // Map tab to API endpoint
    let endpoint = '';
    switch (tabName) {
        case 'real':
            endpoint = '/real-alternatives';
            break;
        case 'tutorials':
            endpoint = '/ai-tutorials';
            break;
        case 'entertainment':
            endpoint = '/ai-entertainment';
            break;
    }

    try {
        // Call backend API via background script to use centralized URL
        if (!isExtensionContextValid()) return;
        const data = await new Promise((resolve, reject) => {
            chrome.runtime.sendMessage({
                type: 'FETCH_API',
                endpoint: endpoint,
                method: 'POST',
                body: {
                    video_id: videoId,
                    detected_subject: detectedSubject,
                    prefer_shorts: preferShorts,
                    max_results: 12
                }
            }, (response) => {
                if (chrome.runtime.lastError) {
                    reject(chrome.runtime.lastError);
                } else if (response && response.success) {
                    resolve(response.data);
                } else {
                    reject(new Error(response?.error || 'Unknown API error'));
                }
            });
        });

        const videos = data.alternatives || [];

        if (videos.length === 0) {
            grid.innerHTML = `
        <div class="yt-empty">
          <div class="yt-empty-icon">\ud83d\ude15</div>
          <div>No videos found</div>
        </div>
      `;
        } else {
            grid.innerHTML = videos.map(v => createVideoCard(v, tabName)).join('');
        }

        // Mark as loaded
        if (!loadedTabs.includes(tabName)) {
            loadedTabs.push(tabName);
            banner.dataset.loadedTabs = loadedTabs.join(',');
        }

    } catch (err) {
        console.error(`Error loading ${tabName}:`, err);
        grid.innerHTML = `
      <div class="yt-empty">
        <div class="yt-empty-icon">\u26a0\ufe0f</div>
        <div>Failed to load videos</div>
        <div style="font-size: 12px; margin-top: 8px;">Is backend running?</div>
      </div>
    `;
    }
}

/**
 * reloadCurrentTab - Reloads the active tab in the AI banner
 * Used when switching formats (Videos/Shorts)
 */
function reloadCurrentTab() {
    const banner = document.getElementById('ai-content-banner');
    if (!banner) return;

    const activeTabBtn = banner.querySelector('.yt-tab.active');
    if (activeTabBtn) {
        const tabName = activeTabBtn.dataset.tab;
        loadTabContent(tabName, true); // Force reload
    }
}
