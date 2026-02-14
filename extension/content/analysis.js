/**
 * YouTube Safety Inspector - Analysis Logic
 * Copyright (c) 2026 beautifulplanet
 * Licensed under MIT License
 */

// State for analysis
let currentVideoId = null;
let isAnalyzing = false;
let lastAnalysisTime = 0;

/**
 * Main function to trigger video analysis
 * @param {string} videoId YouTube Video ID
 * @param {boolean} force Force re-analysis even if recently checked
 */
async function checkVideo(videoId, force = false) {
    try {
        if (!videoId) return;

        // Prevent duplicate checks
        if (videoId === currentVideoId && !force && (Date.now() - lastAnalysisTime < 30000)) {
            return;
        }

        currentVideoId = videoId;
        isAnalyzing = true;
        lastAnalysisTime = Date.now();

        // Hide previous overlays
        if (typeof hideAllOverlays === 'function') hideAllOverlays();

        // Scrape metadata using utils
        const title = typeof getVideoTitle === 'function' ? getVideoTitle() : '';
        const channel = typeof getChannelName === 'function' ? getChannelName() : '';
        const description = typeof getVideoDescription === 'function' ? getVideoDescription() : '';

        // Send message to background script to handle API call
        chrome.runtime.sendMessage({
            type: 'ANALYZE_VIDEO',
            videoId: videoId,
            title: title,
            channel: channel,
            description: description
        }, (response) => {
            isAnalyzing = false;

            if (chrome.runtime.lastError) {
                console.error('\ud83d\udee1\ufe0f Analysis error:', chrome.runtime.lastError);
                return;
            }

            if (response && response.success) {
                processAnalysisResults(response.data);
            } else if (response && response.error) {
                console.error('\ud83d\udee1\ufe0f API Error:', response.error);
            }
        });
    } catch (err) {
        console.error('\ud83d\udee1\ufe0f Error in checkVideo:', err);
        isAnalyzing = false;
    }
}

/**
 * Process results from backend and update UI
 * @param {Object} results Analysis results JSON
 */
function processAnalysisResults(results) {
    try {
        if (results.error) {
            console.error('\ud83d\udee1\ufe0f API Error:', results.error);
            return;
        }

        // 1. Safety Score Check
        // Show overlay if score is low AND has severe warnings
        if (results.safety_score < 35 && results.warnings && results.warnings.length > 0) {
            const severeWarnings = results.warnings.filter(w => w.severity === 'high');

            if (severeWarnings.length > 0) {
                if (typeof injectOverlay === 'function') injectOverlay();

                const scoreEl = document.getElementById('safety-score');
                const commentsEl = document.getElementById('warning-comments');
                const overlay = document.getElementById('safety-overlay');

                if (scoreEl) scoreEl.textContent = results.safety_score;
                if (commentsEl) {
                    commentsEl.innerHTML = results.warnings.map(w =>
                        `<div style="padding: 10px; background: rgba(255,0,0,0.1); border-left: 3px solid #ff4444; margin-bottom: 8px;">
            <div style="font-weight: 700; color: #ff4444; font-size: 13px;">${escapeHtml(w.category)}</div>
            <div style="color: #ddd; font-size: 13px;">${escapeHtml(w.message)}</div>
          </div>`
                    ).join('');
                }

                if (overlay) overlay.style.display = 'flex';

                // Auto-load alternatives for dangerous content
                if (results.alternatives && results.alternatives.length > 0) {
                    const altSection = document.getElementById('alternatives-section');
                    const altList = document.getElementById('alternatives-list');

                    if (altSection && altList) {
                        altSection.style.display = 'block';
                        altList.innerHTML = results.alternatives.map(video => createVideoCard(video)).join('');
                    }
                }
            }
        }

        // 2. AI Content Check
        if (results.ai_generated) {
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
        const data = await new Promise((resolve, reject) => {
            chrome.runtime.sendMessage({
                action: 'fetchAPI',
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
