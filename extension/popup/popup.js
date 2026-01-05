// Configuration
const API_BASE_URL = 'http://localhost:8000';

// Default settings
const DEFAULT_SETTINGS = {
  enableSafety: true,
  enableAIDetection: true,
  enableAlternatives: true,
  enableAIOptions: true,
  autoAnalyze: true,
  bannerStyle: 'minimal'
};

// DOM Elements
const elements = {
  // Main view
  mainView: document.getElementById('main-view'),
  loading: document.getElementById('loading'),
  notYoutube: document.getElementById('not-youtube'),
  results: document.getElementById('results'),
  error: document.getElementById('error'),
  errorMessage: document.getElementById('error-message'),
  scoreCircle: document.getElementById('score-circle'),
  scoreValue: document.getElementById('score-value'),
  scoreLabel: document.getElementById('score-label'),
  warningsSection: document.getElementById('warnings-section'),
  warningsList: document.getElementById('warnings-list'),
  categoriesSection: document.getElementById('categories-section'),
  categoriesList: document.getElementById('categories-list'),
  viewDetails: document.getElementById('view-details'),
  retryBtn: document.getElementById('retry-btn'),
  
  // Settings view
  settingsView: document.getElementById('settings-view'),
  settingsToggle: document.getElementById('settings-toggle'),
  settingsBack: document.getElementById('settings-back'),
  
  // Settings toggles
  enableSafety: document.getElementById('enable-safety'),
  enableAIDetection: document.getElementById('enable-ai-detection'),
  enableAlternatives: document.getElementById('enable-alternatives'),
  enableAIOptions: document.getElementById('enable-ai-options'),
  autoAnalyze: document.getElementById('auto-analyze'),
  resetSettings: document.getElementById('reset-settings'),
  
  // Footer
  apiStatusDot: document.getElementById('api-status-dot'),
  apiStatusText: document.getElementById('api-status-text')
};

// State
let currentVideoId = null;
let cachedResults = {};
let currentSettings = { ...DEFAULT_SETTINGS };

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  await checkApiStatus();
  await analyzeCurrentTab();
  
  // Event listeners - Main view
  elements.retryBtn.addEventListener('click', analyzeCurrentTab);
  elements.viewDetails.addEventListener('click', openFullReport);
  
  // Event listeners - Settings navigation
  elements.settingsToggle.addEventListener('click', showSettingsView);
  elements.settingsBack.addEventListener('click', showMainView);
  
  // Event listeners - Settings toggles
  elements.enableSafety.addEventListener('change', saveSettings);
  elements.enableAIDetection.addEventListener('change', saveSettings);
  elements.enableAlternatives.addEventListener('change', saveSettings);
  elements.enableAIOptions.addEventListener('change', saveSettings);
  elements.autoAnalyze.addEventListener('change', saveSettings);
  elements.resetSettings.addEventListener('click', resetSettings);
  
  // Banner style radio buttons
  document.querySelectorAll('input[name="banner-style"]').forEach(radio => {
    radio.addEventListener('change', saveSettings);
  });
});

// Show settings view
function showSettingsView() {
  elements.mainView.classList.add('hidden');
  elements.settingsView.classList.remove('hidden');
}

// Show main view
function showMainView() {
  elements.settingsView.classList.add('hidden');
  elements.mainView.classList.remove('hidden');
}

// Check if backend API is running
async function checkApiStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { 
      method: 'GET',
      signal: AbortSignal.timeout(3000)
    });
    
    if (response.ok) {
      elements.apiStatusDot.classList.add('connected');
      elements.apiStatusDot.classList.remove('disconnected');
      elements.apiStatusText.textContent = 'API Connected';
      return true;
    }
  } catch (error) {
    console.error('API check failed:', error);
  }
  
  elements.apiStatusDot.classList.add('disconnected');
  elements.apiStatusDot.classList.remove('connected');
  elements.apiStatusText.textContent = 'API Offline';
  return false;
}

// Load user settings
async function loadSettings() {
  try {
    const stored = await chrome.storage.sync.get(['inspectorSettings']);
    if (stored.inspectorSettings) {
      currentSettings = { ...DEFAULT_SETTINGS, ...stored.inspectorSettings };
    }
    
    // Apply to UI
    elements.enableSafety.checked = currentSettings.enableSafety;
    elements.enableAIDetection.checked = currentSettings.enableAIDetection;
    elements.enableAlternatives.checked = currentSettings.enableAlternatives;
    elements.enableAIOptions.checked = currentSettings.enableAIOptions;
    elements.autoAnalyze.checked = currentSettings.autoAnalyze;
    
    // Set banner style
    const styleRadio = document.querySelector(`input[name="banner-style"][value="${currentSettings.bannerStyle}"]`);
    if (styleRadio) styleRadio.checked = true;
    
  } catch (error) {
    console.error('Failed to load settings:', error);
  }
}

// Save user settings
async function saveSettings() {
  currentSettings = {
    enableSafety: elements.enableSafety.checked,
    enableAIDetection: elements.enableAIDetection.checked,
    enableAlternatives: elements.enableAlternatives.checked,
    enableAIOptions: elements.enableAIOptions.checked,
    autoAnalyze: elements.autoAnalyze.checked,
    bannerStyle: document.querySelector('input[name="banner-style"]:checked')?.value || 'minimal'
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
    showSettingsSaved();
  } catch (error) {
    console.error('Failed to save settings:', error);
  }
}

// Reset settings to defaults
async function resetSettings() {
  currentSettings = { ...DEFAULT_SETTINGS };
  
  // Apply to UI
  elements.enableSafety.checked = currentSettings.enableSafety;
  elements.enableAIDetection.checked = currentSettings.enableAIDetection;
  elements.enableAlternatives.checked = currentSettings.enableAlternatives;
  elements.enableAIOptions.checked = currentSettings.enableAIOptions;
  elements.autoAnalyze.checked = currentSettings.autoAnalyze;
  document.querySelector('input[name="banner-style"][value="minimal"]').checked = true;
  
  await saveSettings();
}

// Show saved confirmation
function showSettingsSaved() {
  const btn = elements.resetSettings;
  const originalText = btn.textContent;
  btn.textContent = '✓ Settings Saved';
  btn.style.background = 'rgba(0, 212, 255, 0.2)';
  btn.style.borderColor = 'rgba(0, 212, 255, 0.3)';
  btn.style.color = '#00d4ff';
  
  setTimeout(() => {
    btn.textContent = originalText;
    btn.style.background = '';
    btn.style.borderColor = '';
    btn.style.color = '';
  }, 1500);
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
  elements.scoreValue.textContent = score;
  elements.scoreCircle.style.setProperty('--score-deg', `${score * 3.6}deg`);
  
  // Set score color class
  elements.scoreCircle.classList.remove('danger', 'warning', 'safe');
  if (score < 40) {
    elements.scoreCircle.classList.add('danger');
    elements.scoreLabel.textContent = 'DANGER';
  } else if (score < 70) {
    elements.scoreCircle.classList.add('warning');
    elements.scoreLabel.textContent = 'CAUTION';
  } else {
    elements.scoreCircle.classList.add('safe');
    elements.scoreLabel.textContent = 'SAFE';
  }
  
  // Display warnings
  if (results.warnings && results.warnings.length > 0) {
    elements.warningsSection.classList.remove('hidden');
    elements.warningsList.innerHTML = results.warnings.map(warning => `
      <li>
        <span class="warning-severity ${warning.severity}">${warning.severity}</span>
        ${escapeHtml(warning.message)}
      </li>
    `).join('');
  } else {
    elements.warningsSection.classList.add('hidden');
  }
  
  // Display categories
  if (results.categories) {
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
  elements.loading.classList.add('hidden');
  elements.notYoutube.classList.add('hidden');
  elements.results.classList.add('hidden');
  elements.error.classList.add('hidden');
  
  switch (state) {
    case 'loading':
      elements.loading.classList.remove('hidden');
      break;
    case 'not-youtube':
      elements.notYoutube.classList.remove('hidden');
      break;
    case 'results':
      elements.results.classList.remove('hidden');
      break;
    case 'error':
      elements.error.classList.remove('hidden');
      break;
  }
}

// Show error state
function showError(message) {
  showState('error');
  elements.errorMessage.textContent = message;
}

// Open full report in new tab
function openFullReport() {
  if (currentVideoId) {
    chrome.tabs.create({
      url: `${API_BASE_URL}/report/${currentVideoId}`
    });
  }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
