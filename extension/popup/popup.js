// Configuration
const API_BASE_URL = 'http://localhost:8000';

// DOM Elements
const elements = {
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
  autoAnalyze: document.getElementById('auto-analyze'),
  apiStatusDot: document.getElementById('api-status-dot'),
  apiStatusText: document.getElementById('api-status-text')
};

// State
let currentVideoId = null;
let cachedResults = {};

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
  await checkApiStatus();
  await loadSettings();
  await analyzeCurrentTab();
  
  // Event listeners
  elements.retryBtn.addEventListener('click', analyzeCurrentTab);
  elements.viewDetails.addEventListener('click', openFullReport);
  elements.autoAnalyze.addEventListener('change', saveSettings);
});

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
  elements.apiStatusText.textContent = 'API Offline - Start backend';
  return false;
}

// Load user settings
async function loadSettings() {
  const settings = await chrome.storage.sync.get(['autoAnalyze']);
  elements.autoAnalyze.checked = settings.autoAnalyze !== false;
}

// Save user settings
async function saveSettings() {
  await chrome.storage.sync.set({
    autoAnalyze: elements.autoAnalyze.checked
  });
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
