// YouTube Safety Inspector - Content Script
// Auto-shows warning overlay for dangerous videos + AI content detection
// VERSION: 2.0 - Fixed ad detection for Shorts

console.log('🛡️ ========================================');
console.log('🛡️ YouTube Safety Inspector v2.0 LOADED!');
console.log('🛡️ URL:', location.href);
console.log('🛡️ Is Shorts:', location.pathname.includes('/shorts/'));
console.log('🛡️ ========================================');

// ALERT to prove it loaded (remove after testing)
if (location.pathname.includes('/shorts/')) {
  console.log('🛡️ 🎯 THIS IS A SHORT - AD DETECTION DISABLED');
}

let currentVideoId = null;
let aiBannerShown = false;
let videoEndListener = null;
let aiFlashInterval = null;
let aiContentDetected = false;
let lastAnalyzedVideoId = null;

// User settings (loaded from chrome.storage)
let userSettings = {
  enableSafety: true,
  enableAIDetection: true,
  enableAlternatives: true,
  enableAIOptions: true,
  autoAnalyze: true,
  bannerStyle: 'minimal'
};

// Load settings immediately
loadUserSettings();

// Listen for settings updates from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'SETTINGS_UPDATED') {
    console.log('🛡️ Settings updated:', message.settings);
    userSettings = { ...userSettings, ...message.settings };
    // Re-evaluate current video with new settings
    if (!userSettings.enableAIDetection && !userSettings.enableSafety) {
      hideAllOverlays();
    }
    sendResponse({ success: true });
  }
  return true;
});

// Load user settings from storage
async function loadUserSettings() {
  try {
    const stored = await chrome.storage.sync.get(['inspectorSettings']);
    if (stored.inspectorSettings) {
      userSettings = { ...userSettings, ...stored.inspectorSettings };
      console.log('🛡️ Settings loaded:', userSettings);
    }
  } catch (error) {
    console.error('🛡️ Failed to load settings:', error);
  }
}

// Inject immediately when script loads
injectOverlay();
injectAIBanner();

// Initial check after a short delay
setTimeout(() => {
  console.log('🛡️ Initial video check...');
  checkVideo();
}, 1000);

// Also check on navigation
let lastUrl = location.href;
let lastVideoId = null;
let adCheckActive = false;

setInterval(() => {
  const currentVideoId = getVideoId();
  const isShorts = location.pathname.includes('/shorts/');
  
  // Only trigger re-analysis if the VIDEO ID actually changed (not just URL params)
  if (currentVideoId && currentVideoId !== lastVideoId) {
    console.log('🛡️ Video ID changed from', lastVideoId, 'to', currentVideoId, isShorts ? '(Short)' : '');
    lastVideoId = currentVideoId;
    lastUrl = location.href;
    aiBannerShown = false;
    aiContentDetected = false;
    lastAnalyzedVideoId = null;
    stopPeriodicAIFlash();
    hideAllOverlays();
    checkVideo();
  }
  
  // ONLY check for ads on regular videos - NEVER on Shorts
  if (!isShorts) {
    const adPlaying = isAdPlaying();
    if (adPlaying && !adCheckActive) {
      adCheckActive = true;
      hideAllOverlays();
      console.log('🛡️ Ad started, hiding overlays');
    } else if (!adPlaying && adCheckActive) {
      adCheckActive = false;
      console.log('🛡️ Ad finished');
      // Re-show results if we have them cached
      if (lastAnalyzedVideoId) {
        chrome.runtime.sendMessage(
          { type: 'GET_CACHED_ANALYSIS', videoId: lastAnalyzedVideoId },
          (response) => {
            if (response && response.success && response.data) {
              setTimeout(() => showResults(response.data), 1000);
            }
          }
        );
      }
    }
  }
}, 2000); // Check every 2 seconds

/**
 * Detect if a YouTube ad is currently playing
 * ONLY for regular videos - Shorts don't have pre-roll ads the same way
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
    console.log('🛡️ Ad detected via .ad-showing class');
    return true;
  }
  
  // Method 2: Check for "Skip Ad" button (definitive signal)
  const skipButton = document.querySelector('.ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button');
  if (skipButton && skipButton.offsetParent !== null) {
    console.log('🛡️ Ad detected via skip button');
    return true;
  }
  
  // Method 3: Check for ad preview countdown
  const adPreview = document.querySelector('.ytp-ad-preview-container');
  if (adPreview && adPreview.offsetParent !== null) {
    console.log('🛡️ Ad detected via preview container');
    return true;
  }
  
  // Method 4: Check for ad overlay elements
  const adOverlay = document.querySelector('.ytp-ad-player-overlay');
  if (adOverlay && adOverlay.offsetParent !== null) {
    console.log('🛡️ Ad detected via overlay');
    return true;
  }
  
  return false;
}

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

function injectOverlay() {
  // Remove existing if any
  const existing = document.getElementById('safety-overlay');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.id = 'safety-overlay';
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.95);
    z-index: 999999;
    display: none;
    align-items: center;
    justify-content: center;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    overflow-y: auto;
  `;

  overlay.innerHTML = `
    <div style="text-align: center; max-width: 900px; padding: 40px; margin: auto;">
      <div style="display: flex; gap: 40px; align-items: flex-start; flex-wrap: wrap; justify-content: center;">
        
        <!-- Left side: Warning -->
        <div style="flex: 1; min-width: 300px; max-width: 400px;">
          <div style="font-size: 60px; margin-bottom: 15px; animation: pulse 2s infinite;">⚠️</div>
          <div id="safety-score" style="font-size: 100px; font-weight: 900; color: #ff4444; line-height: 1; margin-bottom: 8px; text-shadow: 0 0 40px rgba(255, 68, 68, 0.5);">--</div>
          <div style="font-size: 28px; font-weight: 800; color: #fff; letter-spacing: 3px; margin-bottom: 8px;">SAFETY WARNING</div>
          <div style="font-size: 14px; color: #888; margin-bottom: 20px;">Community flagged dangerous content</div>
          <div id="warning-comments" style="text-align: left; margin: 20px 0; max-height: 200px; overflow-y: auto;"></div>
          <div style="display: flex; gap: 10px; justify-content: center; margin-top: 20px; flex-wrap: wrap;">
            <button id="btn-proceed" style="padding: 12px 24px; background: transparent; border: 2px solid #666; color: #888; font-size: 13px; font-weight: 600; border-radius: 25px; cursor: pointer;">Watch Anyway</button>
            <button id="btn-leave" style="padding: 12px 24px; background: linear-gradient(135deg, #ff4444 0%, #cc0000 100%); border: none; color: #fff; font-size: 13px; font-weight: 700; border-radius: 25px; cursor: pointer; box-shadow: 0 4px 20px rgba(255, 68, 68, 0.4);">Leave Video</button>
          </div>
        </div>
        
        <!-- Right side: Safe Alternatives -->
        <div id="alternatives-section" style="flex: 1; min-width: 300px; max-width: 450px; text-align: left; display: none;">
          <div style="font-size: 20px; font-weight: 700; color: #4CAF50; margin-bottom: 15px; display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 28px;">✅</span>
            <span id="alternatives-title">Watch These Instead</span>
          </div>
          <div id="alternatives-message" style="font-size: 13px; color: #aaa; margin-bottom: 15px;">Safe, professional alternatives:</div>
          <div id="alternatives-list" style="display: flex; flex-direction: column; gap: 12px;"></div>
        </div>
        
      </div>
    </div>
    <style>
      @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.1); } }
      .alt-video-card {
        display: flex;
        gap: 12px;
        padding: 10px;
        background: rgba(76, 175, 80, 0.1);
        border: 1px solid rgba(76, 175, 80, 0.3);
        border-radius: 10px;
        cursor: pointer;
        transition: all 0.2s ease;
      }
      .alt-video-card:hover {
        background: rgba(76, 175, 80, 0.2);
        border-color: rgba(76, 175, 80, 0.5);
        transform: translateX(5px);
      }
      .alt-video-thumb {
        width: 120px;
        height: 68px;
        border-radius: 6px;
        object-fit: cover;
        flex-shrink: 0;
      }
      .alt-video-info {
        flex: 1;
        overflow: hidden;
      }
      .alt-video-title {
        font-size: 13px;
        font-weight: 600;
        color: #fff;
        margin-bottom: 4px;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
      .alt-video-channel {
        font-size: 11px;
        color: #aaa;
        margin-bottom: 4px;
      }
      .alt-video-badge {
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 4px;
        background: rgba(76, 175, 80, 0.3);
        color: #4CAF50;
        display: inline-block;
      }
    </style>
  `;

  document.body.appendChild(overlay);

  // Button handlers
  document.getElementById('btn-proceed').onclick = () => {
    overlay.style.display = 'none';
  };
  
  document.getElementById('btn-leave').onclick = () => {
    window.history.back();
  };

  console.log('🛡️ Overlay injected');
}

function injectAIBanner() {
  // Remove existing if any
  const existing = document.getElementById('ai-content-banner');
  if (existing) existing.remove();

  // Create YouTube-styled AI content panel
  const banner = document.createElement('div');
  banner.id = 'ai-content-banner';
  banner.style.cssText = `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: #0f0f0f;
    border-radius: 12px;
    padding: 0;
    z-index: 999998;
    display: none;
    font-family: "YouTube Sans", "Roboto", sans-serif;
    box-shadow: 0 24px 80px rgba(0, 0, 0, 0.6);
    animation: yt-modal-in 0.3s ease-out;
    max-width: 800px;
    width: 90vw;
    max-height: 85vh;
    overflow: hidden;
  `;

  banner.innerHTML = `
    <style>
      @keyframes yt-modal-in { 
        from { opacity: 0; transform: translate(-50%, -50%) scale(0.95); } 
        to { opacity: 1; transform: translate(-50%, -50%) scale(1); } 
      }
      
      /* YouTube-style video grid */
      .yt-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 16px;
        padding: 16px;
        max-height: 400px;
        overflow-y: auto;
      }
      
      .yt-grid::-webkit-scrollbar {
        width: 8px;
      }
      
      .yt-grid::-webkit-scrollbar-track {
        background: #272727;
        border-radius: 4px;
      }
      
      .yt-grid::-webkit-scrollbar-thumb {
        background: #717171;
        border-radius: 4px;
      }
      
      .yt-video-card {
        cursor: pointer;
        transition: all 0.2s;
        border-radius: 12px;
        overflow: hidden;
      }
      
      .yt-video-card:hover {
        transform: translateY(-2px);
      }
      
      .yt-video-card:hover .yt-thumb-overlay {
        opacity: 1;
      }
      
      .yt-thumb-container {
        position: relative;
        width: 100%;
        padding-top: 56.25%;
        background: #272727;
        border-radius: 12px;
        overflow: hidden;
      }
      
      .yt-thumb {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
      
      .yt-thumb-overlay {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0,0,0,0.6);
        display: flex;
        align-items: center;
        justify-content: center;
        opacity: 0;
        transition: opacity 0.2s;
      }
      
      .yt-play-icon {
        width: 48px;
        height: 48px;
        background: rgba(255,0,0,0.9);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      
      .yt-play-icon::after {
        content: '';
        border-left: 14px solid white;
        border-top: 8px solid transparent;
        border-bottom: 8px solid transparent;
        margin-left: 3px;
      }
      
      .yt-badge {
        position: absolute;
        bottom: 8px;
        right: 8px;
        padding: 3px 6px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 500;
        background: rgba(0,0,0,0.8);
        color: #4CAF50;
      }
      
      .yt-badge.trusted {
        background: #065fd4;
        color: white;
      }
      
      .yt-video-info {
        padding: 10px 4px;
      }
      
      .yt-video-title {
        font-size: 14px;
        font-weight: 500;
        color: #f1f1f1;
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        margin-bottom: 6px;
      }
      
      .yt-channel-name {
        font-size: 12px;
        color: #aaa;
        display: flex;
        align-items: center;
        gap: 4px;
      }
      
      .yt-verified {
        width: 14px;
        height: 14px;
        fill: #aaa;
      }
      
      .yt-header {
        padding: 16px 20px;
        border-bottom: 1px solid #272727;
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      
      .yt-header-left {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      
      .yt-ai-icon {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #ff6b6b 0%, #ff8e53 100%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
      }
      
      .yt-header-text h2 {
        font-size: 18px;
        font-weight: 600;
        color: #f1f1f1;
        margin: 0 0 2px 0;
      }
      
      .yt-header-text p {
        font-size: 13px;
        color: #aaa;
        margin: 0;
      }
      
      .yt-close-btn {
        background: transparent;
        border: none;
        color: #909090;
        font-size: 24px;
        cursor: pointer;
        padding: 8px;
        border-radius: 50%;
        transition: background 0.2s;
        line-height: 1;
      }
      
      .yt-close-btn:hover {
        background: #272727;
        color: #fff;
      }
      
      .yt-section-title {
        padding: 16px 20px 8px;
        font-size: 16px;
        font-weight: 600;
        color: #f1f1f1;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      
      .yt-footer {
        padding: 12px 20px;
        border-top: 1px solid #272727;
        display: flex;
        gap: 12px;
        justify-content: flex-end;
      }
      
      .yt-btn {
        padding: 10px 16px;
        border-radius: 18px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
      }
      
      .yt-btn-secondary {
        background: transparent;
        border: 1px solid #717171;
        color: #3ea6ff;
      }
      
      .yt-btn-secondary:hover {
        background: rgba(62, 166, 255, 0.1);
        border-color: #3ea6ff;
      }
      
      .yt-btn-primary {
        background: #3ea6ff;
        border: none;
        color: #0f0f0f;
      }
      
      .yt-btn-primary:hover {
        background: #65b8ff;
      }
      
      /* AI Options Section at Bottom */
      .yt-ai-options {
        padding: 16px 20px;
        background: linear-gradient(180deg, #1a1a1a 0%, #0f0f0f 100%);
        border-top: 1px solid #272727;
      }
      
      .yt-ai-options-title {
        font-size: 13px;
        color: #717171;
        margin-bottom: 12px;
        text-align: center;
      }
      
      .yt-ai-options-row {
        display: flex;
        gap: 10px;
        justify-content: center;
        flex-wrap: wrap;
      }
      
      .yt-ai-option-btn {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 16px;
        background: #272727;
        border: 1px solid #3a3a3a;
        border-radius: 20px;
        color: #e0e0e0;
        font-size: 13px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
      }
      
      .yt-ai-option-btn:hover {
        background: #3a3a3a;
        border-color: #4a4a4a;
        transform: translateY(-1px);
      }
      
      .yt-ai-option-btn.learn {
        border-color: #065fd4;
      }
      
      .yt-ai-option-btn.learn:hover {
        background: rgba(6, 95, 212, 0.2);
        border-color: #3ea6ff;
        color: #3ea6ff;
      }
      
      .yt-ai-option-btn.watch {
        border-color: #ff6b6b;
      }
      
      .yt-ai-option-btn.watch:hover {
        background: rgba(255, 107, 107, 0.2);
        border-color: #ff8e53;
        color: #ff8e53;
      }
      
      .yt-format-toggle {
        display: flex;
        gap: 4px;
        padding: 4px;
        background: #1a1a1a;
        border-radius: 16px;
        margin-top: 12px;
        justify-content: center;
      }
      
      .yt-format-btn {
        padding: 6px 14px;
        border: none;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
        color: #909090;
        background: transparent;
      }
      
      .yt-format-btn.active {
        background: #272727;
        color: #f1f1f1;
      }
      
      .yt-format-btn:hover:not(.active) {
        color: #f1f1f1;
      }
      
      /* Loading state */
      .yt-loading {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        padding: 20px;
        color: #909090;
      }
      
      .yt-spinner {
        width: 20px;
        height: 20px;
        border: 2px solid #3a3a3a;
        border-top-color: #3ea6ff;
        border-radius: 50%;
        animation: yt-spin 0.8s linear infinite;
      }
      
      @keyframes yt-spin {
        to { transform: rotate(360deg); }
      }
    </style>
    
    <div class="yt-header">
      <div class="yt-header-left">
        <div class="yt-ai-icon">🤖</div>
        <div class="yt-header-text">
          <h2>AI-Generated Content Detected</h2>
          <p id="ai-banner-message">Community members indicate this may be AI-generated</p>
        </div>
      </div>
      <button class="yt-close-btn" id="ai-banner-close">✕</button>
    </div>
    
    <div id="ai-banner-alternatives" style="display: none;">
      <div class="yt-section-title">
        <span>🎬</span>
        <span id="ai-section-title">Watch Real Videos Instead</span>
      </div>
      <div class="yt-grid" id="ai-alt-grid"></div>
    </div>
    
    <!-- AI Content Options Section -->
    <div class="yt-ai-options" id="ai-options-section">
      <div class="yt-ai-options-title">🎯 Interested in AI content?</div>
      <div class="yt-ai-options-row">
        <button class="yt-ai-option-btn learn" id="ai-learn-btn">
          <span>🎓</span>
          <span>Learn to Make AI Videos</span>
        </button>
        <button class="yt-ai-option-btn watch" id="ai-watch-more-btn">
          <span>🎨</span>
          <span>Watch More AI Content</span>
        </button>
      </div>
      <div class="yt-format-toggle">
        <button class="yt-format-btn active" id="ai-format-long">📺 Long-form</button>
        <button class="yt-format-btn" id="ai-format-shorts">⚡ Shorts</button>
      </div>
    </div>
    
    <div class="yt-footer">
      <button class="yt-btn yt-btn-secondary" id="ai-watch-anyway">Watch Anyway</button>
    </div>
  `;

  document.body.appendChild(banner);

  // Store detected subject for API calls
  banner.dataset.detectedSubject = '';
  banner.dataset.preferShorts = 'false';

  document.getElementById('ai-banner-close').onclick = () => {
    banner.style.display = 'none';
  };
  
  document.getElementById('ai-watch-anyway').onclick = () => {
    banner.style.display = 'none';
  };
  
  // Format toggle handlers
  const longBtn = document.getElementById('ai-format-long');
  const shortsBtn = document.getElementById('ai-format-shorts');
  
  longBtn.onclick = () => {
    longBtn.classList.add('active');
    shortsBtn.classList.remove('active');
    banner.dataset.preferShorts = 'false';
  };
  
  shortsBtn.onclick = () => {
    shortsBtn.classList.add('active');
    longBtn.classList.remove('active');
    banner.dataset.preferShorts = 'true';
  };
  
  // AI Tutorial button - fetch and show tutorials
  document.getElementById('ai-learn-btn').onclick = async () => {
    const subject = banner.dataset.detectedSubject || null;
    const preferShorts = banner.dataset.preferShorts === 'true';
    await fetchAndShowAIContent('tutorials', subject, preferShorts);
  };
  
  // AI Entertainment button - fetch and show AI content
  document.getElementById('ai-watch-more-btn').onclick = async () => {
    const subject = banner.dataset.detectedSubject || null;
    const preferShorts = banner.dataset.preferShorts === 'true';
    await fetchAndShowAIContent('entertainment', subject, preferShorts);
  };

  console.log('🛡️ YouTube-styled AI banner injected with AI content options');
}

// Fetch AI tutorials or entertainment from API
async function fetchAndShowAIContent(type, subject, preferShorts) {
  const banner = document.getElementById('ai-content-banner');
  const altSection = document.getElementById('ai-banner-alternatives');
  const altGrid = document.getElementById('ai-alt-grid');
  const sectionTitle = document.getElementById('ai-section-title');
  
  if (!altGrid || !sectionTitle) return;
  
  // Show loading state
  altGrid.innerHTML = `
    <div class="yt-loading" style="grid-column: 1 / -1;">
      <div class="yt-spinner"></div>
      <span>Finding ${type === 'tutorials' ? 'tutorials' : 'AI videos'}...</span>
    </div>
  `;
  altSection.style.display = 'block';
  
  const endpoint = type === 'tutorials' ? '/ai-tutorials' : '/ai-entertainment';
  const requestBody = {
    subject: subject,
    prefer_shorts: preferShorts,
    max_results: 8
  };
  
  try {
    // Use message passing to go through background script (same as main API)
    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({
        action: 'fetchAPI',
        url: `http://localhost:8000${endpoint}`,
        method: 'POST',
        body: requestBody
      }, response => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else if (response.error) {
          reject(new Error(response.error));
        } else {
          resolve(response);
        }
      });
    });
    
    const alternatives = response.data?.alternatives || [];
    const message = response.data?.message || '';
    
    // Update section title
    if (type === 'tutorials') {
      sectionTitle.innerHTML = '🎓 AI Video Creation Tutorials';
    } else {
      sectionTitle.innerHTML = '🎨 Quality AI Entertainment';
    }
    
    if (alternatives.length > 0) {
      // Build video cards
      altGrid.innerHTML = alternatives.map(video => `
        <div class="yt-video-card" onclick="window.location.href='${video.url}'">
          <div class="yt-thumb-container">
            <img class="yt-thumb" src="${video.thumbnail}" alt="" 
                 onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 320 180%22><rect fill=%22%23272727%22 width=%22320%22 height=%22180%22/><text x=%2250%25%22 y=%2250%25%22 fill=%22%23717171%22 font-size=%2224%22 text-anchor=%22middle%22 dy=%22.3em%22>🎬</text></svg>'">
            <div class="yt-thumb-overlay">
              <div class="yt-play-icon"></div>
            </div>
            <span class="yt-badge ${video.is_trusted ? 'trusted' : ''}">${video.badge || (type === 'tutorials' ? '🎓 Tutorial' : '🤖 AI')}</span>
          </div>
          <div class="yt-video-info">
            <div class="yt-video-title">${escapeHtml(video.title)}</div>
            <div class="yt-channel-name">${escapeHtml(video.channel)}</div>
          </div>
        </div>
      `).join('');
      
      console.log(`🎬 Showing ${alternatives.length} ${type} videos`);
    } else {
      altGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 20px; color: #909090;">
          <p>No ${type} found. Try a different format!</p>
        </div>
      `;
    }
    
  } catch (error) {
    console.error(`Failed to fetch AI ${type}:`, error);
    altGrid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 20px; color: #ff6b6b;">
        <p>⚠️ Couldn't load ${type}. API may be offline.</p>
      </div>
    `;
  }
}

function showAIBanner(message, duration = 0, alternatives = [], detectedAnimal = null) {
  const banner = document.getElementById('ai-content-banner');
  const messageEl = document.getElementById('ai-banner-message');
  const altSection = document.getElementById('ai-banner-alternatives');
  const altGrid = document.getElementById('ai-alt-grid');
  const sectionTitle = document.getElementById('ai-section-title');
  const aiOptionsSection = document.getElementById('ai-options-section');
  
  if (banner && messageEl) {
    messageEl.textContent = message || 'Community members indicate this may be AI-generated';
    
    // Store detected subject for AI content API calls
    if (detectedAnimal) {
      banner.dataset.detectedSubject = detectedAnimal;
      console.log('🐾 Stored detected subject:', detectedAnimal);
    }
    
    // Show/hide AI options section based on user settings
    if (aiOptionsSection) {
      aiOptionsSection.style.display = userSettings.enableAIOptions ? 'block' : 'none';
    }
    
    // Show alternatives in YouTube-style grid if available AND alternatives enabled
    if (altSection && altGrid && alternatives.length > 0 && userSettings.enableAlternatives) {
      // Update section title based on detected animal
      if (sectionTitle) {
        if (detectedAnimal) {
          const animalCap = detectedAnimal.charAt(0).toUpperCase() + detectedAnimal.slice(1);
          sectionTitle.textContent = `Watch Real ${animalCap} Videos Instead`;
        } else {
          sectionTitle.textContent = 'Watch Real Videos Instead';
        }
      }
      
      // Build YouTube-style video cards
      altGrid.innerHTML = alternatives.map(video => `
        <div class="yt-video-card" onclick="window.location.href='${video.url}'">
          <div class="yt-thumb-container">
            <img class="yt-thumb" src="${video.thumbnail}" alt="" 
                 onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 320 180%22><rect fill=%22%23272727%22 width=%22320%22 height=%22180%22/><text x=%2250%25%22 y=%2250%25%22 fill=%22%23717171%22 font-size=%2224%22 text-anchor=%22middle%22 dy=%22.3em%22>🎬</text></svg>'">
            <div class="yt-thumb-overlay">
              <div class="yt-play-icon"></div>
            </div>
            <span class="yt-badge ${video.is_trusted ? 'trusted' : ''}">${video.is_trusted ? '✓ Verified' : '🎬 Real'}</span>
          </div>
          <div class="yt-video-info">
            <div class="yt-video-title">${escapeHtml(video.title)}</div>
            <div class="yt-channel-name">
              ${escapeHtml(video.channel)}
              ${video.is_trusted ? '<svg class="yt-verified" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>' : ''}
            </div>
          </div>
        </div>
      `).join('');
      
      altSection.style.display = 'block';
      console.log('🎬 Showing', alternatives.length, 'real video alternatives in YouTube grid');
    } else if (altSection) {
      altSection.style.display = 'none';
    }
    
    banner.style.display = 'block';
    
    // Auto-hide after duration (0 = don't auto-hide)
    if (duration > 0) {
      setTimeout(() => {
        banner.style.display = 'none';
      }, duration);
    }
  }
}

function showQuickAIFlash(duration = 1500) {
  // Create a brief flash overlay for AI content reminder
  let flash = document.getElementById('ai-flash-overlay');
  
  if (!flash) {
    flash = document.createElement('div');
    flash.id = 'ai-flash-overlay';
    flash.style.cssText = `
      position: fixed;
      top: 10px;
      right: 10px;
      background: linear-gradient(135deg, rgba(0, 212, 255, 0.95) 0%, rgba(0, 150, 200, 0.95) 100%);
      border-radius: 12px;
      padding: 12px 18px;
      z-index: 999997;
      display: none;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      box-shadow: 0 4px 20px rgba(0, 212, 255, 0.5);
      animation: flash-slide-in 0.3s ease-out;
    `;
    
    flash.innerHTML = `
      <style>
        @keyframes flash-slide-in { 
          from { opacity: 0; transform: translateX(100px); } 
          to { opacity: 1; transform: translateX(0); } 
        }
        @keyframes flash-slide-out { 
          from { opacity: 1; transform: translateX(0); } 
          to { opacity: 0; transform: translateX(100px); } 
        }
      </style>
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

function startPeriodicAIFlash() {
  // Clear any existing interval
  if (aiFlashInterval) {
    clearInterval(aiFlashInterval);
  }
  
  // Flash every 45 seconds while video is playing (but not during ads)
  aiFlashInterval = setInterval(() => {
    const video = document.querySelector('video');
    // Don't flash during ads
    if (video && !video.paused && aiContentDetected && !isAdPlaying()) {
      showQuickAIFlash(1500);
      console.log('🤖 AI content reminder flash');
    }
  }, 45000); // Every 45 seconds
}

function stopPeriodicAIFlash() {
  if (aiFlashInterval) {
    clearInterval(aiFlashInterval);
    aiFlashInterval = null;
  }
}

function setupVideoEndListener(aiMessage) {
  // Find the video element
  const video = document.querySelector('video');
  if (!video) return;

  // Remove old listener if exists
  if (videoEndListener) {
    video.removeEventListener('ended', videoEndListener);
    video.removeEventListener('timeupdate', videoEndListener);
  }

  // Show banner when video ends or near the end (but not during ads)
  videoEndListener = () => {
    if (video.duration && video.currentTime >= video.duration - 3 && !isAdPlaying()) {
      showAIBanner(aiMessage + ' (Reminder: Verify AI content authenticity)', 6000);
    }
  };

  video.addEventListener('timeupdate', videoEndListener);
}

async function checkVideo() {
  const isShorts = location.pathname.includes('/shorts/');
  const videoId = getVideoId();
  
  console.log('🛡️ ========================================');
  console.log('🛡️ checkVideo() called');
  console.log('🛡️ Video ID:', videoId);
  console.log('🛡️ Is Shorts:', isShorts);
  console.log('🛡️ URL:', location.href);
  console.log('🛡️ Settings:', JSON.stringify(userSettings));
  console.log('🛡️ Last analyzed:', lastAnalyzedVideoId);
  console.log('🛡️ ========================================');
  
  if (!videoId) {
    console.log('🛡️ ❌ No video ID found - returning');
    return;
  }
  
  // Check if auto-analyze is enabled
  if (!userSettings.autoAnalyze) {
    console.log('🛡️ ❌ Auto-analyze disabled, skipping');
    return;
  }
  
  // Check if both features are disabled - nothing to do
  if (!userSettings.enableSafety && !userSettings.enableAIDetection) {
    console.log('🛡️ ❌ All detection features disabled');
    return;
  }
  
  // Skip if we already analyzed this video
  if (videoId === lastAnalyzedVideoId) {
    console.log('🛡️ ⏭️ Already analyzed this video:', lastAnalyzedVideoId);
    return;
  }

  // For regular videos (not Shorts), skip if ad is playing
  // NEVER skip for Shorts!
  if (!isShorts && isAdPlaying()) {
    console.log('🛡️ ⏳ Ad detected on regular video, waiting...');
    setTimeout(() => {
      if (!isAdPlaying()) checkVideo();
    }, 5000);
    return;
  }

  console.log('🛡️ ✅ *** STARTING ANALYSIS *** Video:', videoId, isShorts ? '(Short)' : '(Regular)');
  lastAnalyzedVideoId = videoId;

  // For regular videos, wait 2 seconds. For Shorts, go immediately.
  if (!isShorts) {
    await new Promise(resolve => setTimeout(resolve, 2000));
  }

  console.log('🛡️ 📤 Sending ANALYZE_VIDEO to background...');
  
  chrome.runtime.sendMessage(
    { type: 'ANALYZE_VIDEO', videoId: videoId },
    (response) => {
      console.log('🛡️ 📥 Response from background:', response);
      console.log('🛡️ Last error:', chrome.runtime.lastError);
      
      if (chrome.runtime.lastError) {
        console.error('🛡️ ❌ Extension error:', chrome.runtime.lastError.message);
        return;
      }
      
      if (response && response.success) {
        console.log('🛡️ ✅ Analysis received! Warnings:', response.data?.warnings?.length || 0);
        showResults(response.data);
      } else {
        console.error('🛡️ ❌ Analysis failed:', response?.error || 'Unknown error');
      }
    }
  );
}

function showResults(results) {
  console.log('🛡️ showResults called with:', JSON.stringify(results, null, 2).substring(0, 500));
  
  const overlay = document.getElementById('safety-overlay');
  const scoreEl = document.getElementById('safety-score');
  const commentsEl = document.getElementById('warning-comments');
  const aiBanner = document.getElementById('ai-content-banner');

  if (!overlay || !aiBanner) {
    console.log('🛡️ Overlay missing, injecting...');
    if (!overlay) injectOverlay();
    if (!aiBanner) injectAIBanner();
    return showResults(results);
  }

  const score = results.safety_score || 0;
  const warnings = results.warnings || [];
  const isTrustedChannel = results.is_trusted_channel || false;
  
  // Skip AI detection for trusted channels (BBC Earth, Nat Geo, etc.)
  if (isTrustedChannel) {
    console.log('🛡️ Trusted channel:', results.channel, '- skipping AI warnings');
  }
  
  // Check for AI content - look for AI category warnings OR vision analysis
  // BUT skip for trusted channels AND if AI detection is disabled
  const visionDetectedAI = results.vision_analysis?.is_ai_generated;
  const visionConcerns = results.vision_analysis?.concerns || [];
  
  const aiWarnings = (isTrustedChannel || !userSettings.enableAIDetection) ? [] : warnings.filter(w => 
    w.category === 'AI Content' || 
    w.category === 'AI Generated Content' ||
    w.category === 'AI Vision Analysis' ||
    (w.message && (
      w.message.toLowerCase().includes('ai ') ||
      w.message.toLowerCase().includes(' ai') ||
      w.message.toLowerCase().match(/\bai\b/) ||  // Match standalone "ai"
      w.message.toLowerCase().includes('fake') ||
      w.message.toLowerCase().includes('generated') ||
      w.message.toLowerCase().includes('deepfake') ||
      w.message.toLowerCase().includes('sora') ||  // Common AI video tool
      w.message.toLowerCase().includes('not real') ||
      w.message.toLowerCase().includes('cgi')
    ))
  );
  
  console.log('🤖 AI detection check - enabled:', userSettings.enableAIDetection, 'warnings:', warnings.length, 'AI warnings found:', aiWarnings.length, 'aiBannerShown:', aiBannerShown);
  
  // Show AI banner if AI content detected (comments, vision, or both)
  // BUT NOT for trusted channels AND only if AI detection is enabled
  if (userSettings.enableAIDetection && (aiWarnings.length > 0 || (visionDetectedAI && !isTrustedChannel)) && !aiBannerShown) {
    aiBannerShown = true;
    aiContentDetected = true;
    
    let aiMessage = 'Community members indicate this may be AI-generated content';
    if (visionDetectedAI) {
      aiMessage = '🔍 AI Vision Analysis detected this appears to be AI-generated content';
    }
    
    // Get alternatives for AI content
    const aiAlternatives = results.safe_alternatives?.alternatives || [];
    const detectedAnimal = results.safe_alternatives?.detected_animal || null;
    
    // Show YouTube-style modal with video grid (don't auto-hide since user needs to browse)
    setTimeout(() => {
      showAIBanner(aiMessage, 0, aiAlternatives, detectedAnimal);
    }, 1500);
    
    // Start periodic flashing every 60 seconds as subtle reminder
    setTimeout(() => {
      startPeriodicAIFlash();
    }, 10000);
    
    // Setup end-of-video listener
    setTimeout(() => {
      setupVideoEndListener('Remember: This content may be AI-generated');
    }, 3000);
    
    console.log('🤖 AI content detected:', aiWarnings.length, 'indicators, Vision AI:', visionDetectedAI, 'Alternatives:', aiAlternatives.length, 'Animal:', detectedAnimal);
  }
  
  // Only count HIGH severity community warnings (real danger signals)
  // Skip if safety warnings are disabled
  const highSeverityWarnings = userSettings.enableSafety ? warnings.filter(w => 
    (w.severity === 'high' || w.severity === 'critical') &&
    w.category !== 'AI Generated Content' // Don't count AI as danger
  ) : [];
  
  // Check for critical child safety warnings (always show these!)
  const childSafetyWarnings = warnings.filter(w => 
    w.category === 'Child Safety' || 
    w.severity === 'critical' ||
    (w.message && w.message.includes('SAFETY'))
  );
  
  console.log('🛡️ Safety analysis:', {
    score: score,
    totalWarnings: warnings.length,
    highSeverityWarnings: highSeverityWarnings.length,
    childSafetyWarnings: childSafetyWarnings.length,
    enableSafety: userSettings.enableSafety,
    warningCategories: warnings.map(w => w.category)
  });
  
  // CRITERIA: Show overlay if safety is enabled AND:
  // 1. ANY child safety warning (critical!), OR
  // 2. Score is VERY low (< 35) AND has multiple warnings, OR
  // 3. Has 3+ high-severity community warnings about danger
  const isDangerous = userSettings.enableSafety && (
    childSafetyWarnings.length > 0 ||  // Always show child safety warnings!
    (score < 35 && highSeverityWarnings.length >= 2) || 
    highSeverityWarnings.length >= 3
  );

  if (!isDangerous) {
    console.log('🛡️ Video appears safe, score:', score, 'high-severity warnings:', highSeverityWarnings.length, 'child safety:', childSafetyWarnings.length);
    overlay.style.display = 'none';
    return;
  }

  console.log('🛡️ DANGER! Score:', score, 'High-severity warnings:', highSeverityWarnings.length, 'Child safety:', childSafetyWarnings.length);

  // Update score
  scoreEl.textContent = score;

  // Combine all warnings to show (child safety + high severity)
  const allDangerWarnings = [...childSafetyWarnings, ...highSeverityWarnings.filter(w => 
    !childSafetyWarnings.some(cs => cs.message === w.message)
  )];

  // Show warning comments
  if (allDangerWarnings.length > 0) {
    commentsEl.innerHTML = allDangerWarnings.slice(0, 5).map(w => `
      <div style="display: flex; align-items: flex-start; gap: 10px; padding: 10px 15px; margin-bottom: 8px; background: ${w.category === 'Child Safety' ? 'rgba(255, 152, 0, 0.2)' : 'rgba(255, 68, 68, 0.15)'}; border-left: 3px solid ${w.category === 'Child Safety' ? '#ff9800' : '#ff4444'}; border-radius: 0 8px 8px 0;">
        <span style="font-size: 16px;">${w.category === 'Child Safety' ? '👶⚠️' : '💬'}</span>
        <span style="color: #eee; font-size: 12px; line-height: 1.4;">${escapeHtml(w.message)}</span>
      </div>
    `).join('');
  }

  // Show safe alternatives if available AND if alternatives are enabled
  const alternatives = results.safe_alternatives?.alternatives || [];
  const altSection = document.getElementById('alternatives-section');
  const altList = document.getElementById('alternatives-list');
  const altTitle = document.getElementById('alternatives-title');
  const altMessage = document.getElementById('alternatives-message');
  
  if (altSection && altList && alternatives.length > 0 && userSettings.enableAlternatives) {
    // Customize title based on content type
    const categoryType = results.safe_alternatives?.category_type || '';
    if (categoryType === 'real_animals') {
      altTitle.textContent = '🦁 Watch REAL Animals Instead';
      altMessage.textContent = 'Verified real footage from trusted sources:';
    } else {
      altTitle.textContent = '✅ Safe Alternatives';
      altMessage.textContent = 'Professional, safe tutorials on the same topic:';
    }
    
    // Build alternative video cards
    altList.innerHTML = alternatives.slice(0, 4).map(video => `
      <div class="alt-video-card" onclick="window.location.href='${video.url}'">
        <img class="alt-video-thumb" src="${video.thumbnail}" alt="" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22120%22 height=%2268%22><rect fill=%22%23333%22 width=%22120%22 height=%2268%22/></svg>'">
        <div class="alt-video-info">
          <div class="alt-video-title">${escapeHtml(video.title)}</div>
          <div class="alt-video-channel">${escapeHtml(video.channel)}</div>
          <span class="alt-video-badge">${video.badge || '📚 Educational'}</span>
        </div>
      </div>
    `).join('');
    
    altSection.style.display = 'block';
    console.log('🛡️ Showing', alternatives.length, 'safe alternatives');
  } else if (altSection) {
    altSection.style.display = 'none';
  }

  // Add YouTube API attribution (required by TOS)
  addYouTubeAttribution(overlay);

  // Show the overlay!
  overlay.style.display = 'flex';
}

/**
 * Add YouTube API attribution (required by YouTube TOS)
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

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
