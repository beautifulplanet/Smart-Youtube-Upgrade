// Configuration - API URL can be overridden in settings for production
// Default is localhost for development
const DEFAULT_API_URL = 'http://localhost:8000';
let API_BASE_URL = DEFAULT_API_URL;

// Load API URL from storage (allows configuration for production)
async function loadApiUrl() {
  try {
    const stored = await chrome.storage.sync.get(['apiBaseUrl']);
    if (stored.apiBaseUrl) {
      API_BASE_URL = stored.apiBaseUrl;
    }
  } catch (e) {
    console.warn('Could not load API URL from storage, using default');
  }
}

// Default settings - comprehensive list
const DEFAULT_SETTINGS = {
  // Detection
  enableSafety: true,
  enableAIDetection: true,
  autoAnalyze: true,
  
  // Video Types
  enableRegularVideos: true,
  enableShorts: true,
  
  // Suggestions
  enableAlternatives: true,
  enableAITutorials: true,
  enableAIEntertainment: true,
  
  // Banner Behavior
  bannerStyle: 'modal',
  autoDismiss: 0,
  enableReminders: true,
  enableEndAlert: true,
  
  // Alerts
  enableSound: false,
  enableVisualEffects: true,
  
  // Sensitivity
  aiSensitivity: 'medium',
  safetySensitivity: 'medium',
  
  // Privacy
  enableAnalytics: false,
  enableCache: true,
  
  // Trusted Channels
  trustedChannels: ['National Geographic', 'BBC Earth', 'The Dodo', 'Discovery', 'Smithsonian Channel', 'PBS Nature']
};

// State
let currentVideoId = null;
let cachedResults = {};
let currentSettings = { ...DEFAULT_SETTINGS };

// DOM Elements cache
const elements = {
  loading: null,
  notYoutube: null,
  results: null,
  error: null,
  errorMessage: null,
  scoreValue: null,
  scoreCircle: null,
  scoreLabel: null,
  warningsSection: null,
  warningsList: null,
  categoriesList: null
};

// Initialize DOM elements
function initElements() {
  elements.loading = document.getElementById('loading');
  elements.notYoutube = document.getElementById('not-youtube');
  elements.results = document.getElementById('results');
  elements.error = document.getElementById('error');
  elements.errorMessage = document.getElementById('error-message');
  elements.scoreValue = document.getElementById('score-value');
  elements.scoreCircle = document.getElementById('score-circle');
  elements.scoreLabel = document.getElementById('score-label');
  elements.warningsSection = document.getElementById('warnings-section');
  elements.warningsList = document.getElementById('warnings-list');
  elements.categoriesList = document.getElementById('categories-list');
}

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
  console.log('Popup loaded, initializing...');
  
  // Initialize DOM element references
  initElements();
  
  await loadSettings();
  await checkApiStatus();
  await analyzeCurrentTab();
  
  // Event listeners - Main view
  document.getElementById('retry-btn')?.addEventListener('click', analyzeCurrentTab);
  document.getElementById('view-details')?.addEventListener('click', openFullReport);
  
  // Event listeners - Settings navigation
  const settingsBtn = document.getElementById('settings-toggle');
  console.log('Settings button found:', settingsBtn);
  if (settingsBtn) {
    settingsBtn.addEventListener('click', () => {
      console.log('Settings button clicked!');
      showSettingsView();
    });
  }
  document.getElementById('settings-back')?.addEventListener('click', showMainView);
  
  // Event listeners - All toggles and selects
  setupSettingsListeners();
  
  // Settings actions
  document.getElementById('reset-settings')?.addEventListener('click', resetSettings);
  document.getElementById('export-settings')?.addEventListener('click', exportSettings);
  document.getElementById('import-settings')?.addEventListener('click', importSettings);
  document.getElementById('add-trusted-btn')?.addEventListener('click', addTrustedChannel);
  
  // Enter key for adding trusted channel
  document.getElementById('new-trusted-channel')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') addTrustedChannel();
  });
});

// Setup all settings input listeners
function setupSettingsListeners() {
  // Toggle checkboxes
  const toggles = [
    'enable-safety', 'enable-ai-detection', 'auto-analyze',
    'enable-regular-videos', 'enable-shorts',
    'enable-alternatives', 'enable-ai-tutorials', 'enable-ai-entertainment',
    'enable-reminders', 'enable-end-alert',
    'enable-sound', 'enable-visual-effects',
    'enable-analytics', 'enable-cache'
  ];
  
  toggles.forEach(id => {
    document.getElementById(id)?.addEventListener('change', saveSettings);
  });
  
  // Select dropdowns
  const selects = ['banner-style', 'auto-dismiss', 'ai-sensitivity', 'safety-sensitivity'];
  selects.forEach(id => {
    document.getElementById(id)?.addEventListener('change', saveSettings);
  });
}

// Show settings view
function showSettingsView() {
  document.getElementById('main-view').classList.add('hidden');
  document.getElementById('settings-view').classList.remove('hidden');
}

// Show main view
function showMainView() {
  document.getElementById('settings-view').classList.add('hidden');
  document.getElementById('main-view').classList.remove('hidden');
}

// Check if backend API is running
async function checkApiStatus() {
  const dot = document.getElementById('api-status-dot');
  const text = document.getElementById('api-status-text');
  
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { 
      method: 'GET',
      signal: AbortSignal.timeout(3000)
    });
    
    if (response.ok) {
      dot?.classList.add('connected');
      dot?.classList.remove('disconnected');
      if (text) text.textContent = 'API Connected';
      return true;
    }
  } catch (error) {
    console.error('API check failed:', error);
  }
  
  dot?.classList.add('disconnected');
  dot?.classList.remove('connected');
  if (text) text.textContent = 'API Offline';
  return false;
}

// Load user settings
async function loadSettings() {
  try {
    const stored = await chrome.storage.sync.get(['inspectorSettings']);
    if (stored.inspectorSettings) {
      currentSettings = { ...DEFAULT_SETTINGS, ...stored.inspectorSettings };
    }
    
    applySettingsToUI();
    renderTrustedChannels();
    
  } catch (error) {
    console.error('Failed to load settings:', error);
  }
}

// Apply settings to UI elements
function applySettingsToUI() {
  // Toggles
  setCheckbox('enable-safety', currentSettings.enableSafety);
  setCheckbox('enable-ai-detection', currentSettings.enableAIDetection);
  setCheckbox('auto-analyze', currentSettings.autoAnalyze);
  setCheckbox('enable-regular-videos', currentSettings.enableRegularVideos);
  setCheckbox('enable-shorts', currentSettings.enableShorts);
  setCheckbox('enable-alternatives', currentSettings.enableAlternatives);
  setCheckbox('enable-ai-tutorials', currentSettings.enableAITutorials);
  setCheckbox('enable-ai-entertainment', currentSettings.enableAIEntertainment);
  setCheckbox('enable-reminders', currentSettings.enableReminders);
  setCheckbox('enable-end-alert', currentSettings.enableEndAlert);
  setCheckbox('enable-sound', currentSettings.enableSound);
  setCheckbox('enable-visual-effects', currentSettings.enableVisualEffects);
  setCheckbox('enable-analytics', currentSettings.enableAnalytics);
  setCheckbox('enable-cache', currentSettings.enableCache);
  
  // Selects
  setSelect('banner-style', currentSettings.bannerStyle);
  setSelect('auto-dismiss', currentSettings.autoDismiss);
  setSelect('ai-sensitivity', currentSettings.aiSensitivity);
  setSelect('safety-sensitivity', currentSettings.safetySensitivity);
}

function setCheckbox(id, value) {
  const el = document.getElementById(id);
  if (el) el.checked = value;
}

function setSelect(id, value) {
  const el = document.getElementById(id);
  if (el) el.value = value;
}

// Escape HTML to prevent XSS - defined early for use in trusted channels
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Save user settings
async function saveSettings() {
  currentSettings = {
    // Detection
    enableSafety: document.getElementById('enable-safety')?.checked ?? true,
    enableAIDetection: document.getElementById('enable-ai-detection')?.checked ?? true,
    autoAnalyze: document.getElementById('auto-analyze')?.checked ?? true,
    
    // Video Types
    enableRegularVideos: document.getElementById('enable-regular-videos')?.checked ?? true,
    enableShorts: document.getElementById('enable-shorts')?.checked ?? true,
    
    // Suggestions
    enableAlternatives: document.getElementById('enable-alternatives')?.checked ?? true,
    enableAITutorials: document.getElementById('enable-ai-tutorials')?.checked ?? true,
    enableAIEntertainment: document.getElementById('enable-ai-entertainment')?.checked ?? true,
    
    // Banner Behavior
    bannerStyle: document.getElementById('banner-style')?.value || 'modal',
    autoDismiss: parseInt(document.getElementById('auto-dismiss')?.value || '0'),
    enableReminders: document.getElementById('enable-reminders')?.checked ?? true,
    enableEndAlert: document.getElementById('enable-end-alert')?.checked ?? true,
    
    // Alerts
    enableSound: document.getElementById('enable-sound')?.checked ?? false,
    enableVisualEffects: document.getElementById('enable-visual-effects')?.checked ?? true,
    
    // Sensitivity
    aiSensitivity: document.getElementById('ai-sensitivity')?.value || 'medium',
    safetySensitivity: document.getElementById('safety-sensitivity')?.value || 'medium',
    
    // Privacy
    enableAnalytics: document.getElementById('enable-analytics')?.checked ?? false,
    enableCache: document.getElementById('enable-cache')?.checked ?? true,
    
    // Keep trusted channels
    trustedChannels: currentSettings.trustedChannels || DEFAULT_SETTINGS.trustedChannels
  };
  
  try {
    await chrome.storage.sync.set({ inspectorSettings: currentSettings });
    
    // Notify content script of settings change
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.id && tab.url?.includes('youtube.com')) {
      chrome.tabs.sendMessage(tab.id, { 
        type: 'SETTINGS_UPDATED', 
        settings: currentSettings 
      }).catch(() => {}); // Ignore if content script not ready
    }
    
    // Show brief confirmation
    showSavedIndicator();
  } catch (error) {
    console.error('Failed to save settings:', error);
  }
}

// Reset settings to defaults
async function resetSettings() {
  if (!confirm('Reset all settings to defaults?')) return;
  
  currentSettings = { ...DEFAULT_SETTINGS };
  applySettingsToUI();
  renderTrustedChannels();
  await saveSettings();
}

// Export settings to JSON
function exportSettings() {
  const dataStr = JSON.stringify(currentSettings, null, 2);
  const blob = new Blob([dataStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  
  const a = document.createElement('a');
  a.href = url;
  a.download = 'youtube-safety-inspector-settings.json';
  a.click();
  
  URL.revokeObjectURL(url);
}

// Import settings from JSON
function importSettings() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.json';
  
  input.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    try {
      const text = await file.text();
      const imported = JSON.parse(text);
      currentSettings = { ...DEFAULT_SETTINGS, ...imported };
      applySettingsToUI();
      renderTrustedChannels();
      await saveSettings();
      alert('Settings imported successfully!');
    } catch (error) {
      alert('Failed to import settings: ' + error.message);
    }
  };
  
  input.click();
}

// Trusted Channels Management
function renderTrustedChannels() {
  const list = document.getElementById('trusted-channels-list');
  if (!list) return;
  
  const channels = currentSettings.trustedChannels || [];
  
  if (channels.length === 0) {
    list.innerHTML = '<div class="trusted-empty">No trusted channels. Add some below!</div>';
    return;
  }
  
  list.innerHTML = channels.map(channel => `
    <div class="trusted-item">
      <span>${escapeHtml(channel)}</span>
      <button class="remove-btn" data-channel="${escapeHtml(channel)}">✕</button>
    </div>
  `).join('');
  
  // Add remove listeners
  list.querySelectorAll('.remove-btn').forEach(btn => {
    btn.addEventListener('click', () => removeTrustedChannel(btn.dataset.channel));
  });
}

function addTrustedChannel() {
  const input = document.getElementById('new-trusted-channel');
  const channel = input.value.trim();
  
  if (!channel) return;
  if (currentSettings.trustedChannels.includes(channel)) {
    alert('Channel already in list');
    return;
  }
  
  currentSettings.trustedChannels.push(channel);
  input.value = '';
  renderTrustedChannels();
  saveSettings();
}

function removeTrustedChannel(channel) {
  currentSettings.trustedChannels = currentSettings.trustedChannels.filter(c => c !== channel);
  renderTrustedChannels();
  saveSettings();
}

// Show saved indicator
function showSavedIndicator() {
  const indicator = document.createElement('div');
  indicator.textContent = '✓ Saved';
  indicator.style.cssText = `
    position: fixed;
    top: 10px;
    right: 10px;
    background: rgba(0, 212, 255, 0.9);
    color: #fff;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    z-index: 9999;
    animation: fadeInOut 1.5s ease;
  `;
  
  // Add animation keyframes if not exists
  if (!document.getElementById('saved-animation-style')) {
    const style = document.createElement('style');
    style.id = 'saved-animation-style';
    style.textContent = `
      @keyframes fadeInOut {
        0% { opacity: 0; transform: translateY(-10px); }
        20% { opacity: 1; transform: translateY(0); }
        80% { opacity: 1; transform: translateY(0); }
        100% { opacity: 0; transform: translateY(-10px); }
      }
    `;
    document.head.appendChild(style);
  }
  
  document.body.appendChild(indicator);
  setTimeout(() => indicator.remove(), 1500);
}

// Get current tab and analyze if YouTube
async function analyzeCurrentTab() {
  showState('loading');
  
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    if (!tab.url || !tab.url.includes('youtube.com/watch')) {
      showState('not-youtube');
      return;
    }
    
    const videoId = extractVideoId(tab.url);
    if (!videoId) {
      showState('not-youtube');
      return;
    }
    
    currentVideoId = videoId;
    
    // Check cache first
    if (cachedResults[videoId]) {
      displayResults(cachedResults[videoId]);
      return;
    }
    
    // Call API for analysis
    const results = await analyzeVideo(videoId);
    cachedResults[videoId] = results;
    displayResults(results);
    
  } catch (error) {
    console.error('Analysis error:', error);
    showError(error.message || 'Failed to analyze video');
  }
}

// Extract video ID from YouTube URL
function extractVideoId(url) {
  const match = url.match(/[?&]v=([^&]+)/);
  return match ? match[1] : null;
}

// Call backend API to analyze video
async function analyzeVideo(videoId) {
  const response = await fetch(`${API_BASE_URL}/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ video_id: videoId })
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Analysis failed');
  }
  
  return response.json();
}

// Display analysis results
function displayResults(results) {
  showState('results');
  
  // Update score
  const score = results.safety_score || 0;
  if (elements.scoreValue) elements.scoreValue.textContent = score;
  if (elements.scoreCircle) elements.scoreCircle.style.setProperty('--score-deg', `${score * 3.6}deg`);
  
  // Set score color class
  elements.scoreCircle?.classList.remove('danger', 'warning', 'safe');
  if (score < 40) {
    elements.scoreCircle?.classList.add('danger');
    if (elements.scoreLabel) elements.scoreLabel.textContent = 'DANGER';
  } else if (score < 70) {
    elements.scoreCircle?.classList.add('warning');
    if (elements.scoreLabel) elements.scoreLabel.textContent = 'CAUTION';
  } else {
    elements.scoreCircle?.classList.add('safe');
    if (elements.scoreLabel) elements.scoreLabel.textContent = 'SAFE';
  }
  
  // Display warnings
  if (results.warnings && results.warnings.length > 0) {
    elements.warningsSection?.classList.remove('hidden');
    if (elements.warningsList) {
      elements.warningsList.innerHTML = results.warnings.map(warning => `
        <li>
          <span class="warning-severity ${warning.severity}">${warning.severity}</span>
          ${escapeHtml(warning.message)}
        </li>
      `).join('');
    }
  } else {
    elements.warningsSection?.classList.add('hidden');
  }
  
  // Display categories
  if (results.categories && elements.categoriesList) {
    elements.categoriesList.innerHTML = Object.entries(results.categories).map(([name, data]) => `
      <div class="category-badge ${data.flagged ? 'flagged' : 'safe'}">
        <span class="emoji">${data.emoji || '📋'}</span>
        ${escapeHtml(name)}
      </div>
    `).join('');
  }
}

// Show/hide state views
function showState(state) {
  elements.loading?.classList.add('hidden');
  elements.notYoutube?.classList.add('hidden');
  elements.results?.classList.add('hidden');
  elements.error?.classList.add('hidden');
  
  switch (state) {
    case 'loading':
      elements.loading?.classList.remove('hidden');
      break;
    case 'not-youtube':
      elements.notYoutube?.classList.remove('hidden');
      break;
    case 'results':
      elements.results?.classList.remove('hidden');
      break;
    case 'error':
      elements.error?.classList.remove('hidden');
      break;
  }
}

// Show error state
function showError(message) {
  showState('error');
  if (elements.errorMessage) elements.errorMessage.textContent = message;
}

// Open full report in new tab
function openFullReport() {
  if (currentVideoId) {
    chrome.tabs.create({
      url: `${API_BASE_URL}/report/${currentVideoId}`
    });
  }
}
