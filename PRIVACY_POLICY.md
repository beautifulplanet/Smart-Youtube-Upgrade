# Privacy Policy — YouTube Safety Inspector

**Last updated:** February 23, 2026  
**Extension version:** 3.0.1

## Overview

YouTube Safety Inspector analyzes YouTube videos for potentially dangerous or misleading content and AI-generated material. This policy explains what data the extension accesses, how it is processed, and your choices.

## Data Collected

### Video Metadata (Processed Locally & via Backend)
When you visit a YouTube video or Short, the extension collects:
- **Video ID** (the 11-character YouTube identifier)
- **Video title** (as displayed on the page)
- **Channel name** (the uploader's public name)
- **Video description** (first 500 characters)

This data is sent to the analysis backend (see "Backend Communication" below) solely to evaluate the video's safety score. **No personal information, account details, browsing history, or cookies are transmitted.**

### Related Video Data (Processed Locally)
The extension reads YouTube's internal API responses on the page to extract related video suggestions (titles, channels, durations). This data **never leaves your browser** — it is used locally to populate the sidebar.

### Settings (Stored Locally)
Your configuration preferences (sensitivity levels, trusted channel list, toggle states) are stored in `chrome.storage.sync` so they persist across devices you are signed into. No settings data is sent to third parties.

## Backend Communication

The extension communicates with a backend API server to perform safety analysis. By default, this is a **local server** you run yourself (`localhost:8000`). If you configure a remote API URL, the extension sends only the video metadata listed above to that URL.

- **No authentication tokens** or YouTube account data are sent.
- **No personally identifiable information** is transmitted.
- The backend processes the request and returns a safety score, category breakdown, and warnings. **No video metadata is stored on the backend after the response is sent.**

## Data Retention

| Data | Location | Retention |
|------|----------|-----------|
| Analysis results cache | Browser session storage | Cleared when browser closes |
| Daily request count | Browser local storage | Resets each calendar day |
| User settings | Chrome sync storage | Until you reset or uninstall |
| Video metadata | Backend (in-memory only) | Discarded after each request |

## Permissions Justification

| Permission | Why It's Needed |
|------------|----------------|
| `activeTab` | Read the current YouTube page to extract video metadata for analysis |
| `storage` | Save your settings and cache analysis results locally |
| Host: `youtube.com` | Content scripts run on YouTube to detect videos and display safety UI |
| Host: backend URL | Send video metadata to the analysis backend and receive safety scores |

## Third-Party Services

- **YouTube Data API**: Video metadata displayed in the extension originates from YouTube's public page data. See [YouTube Terms of Service](https://www.youtube.com/t/terms) and [Google Privacy Policy](https://policies.google.com/privacy).
- **No analytics, advertising, or tracking services** are used by this extension.

## Your Choices

- **Disable auto-analyze**: Turn off automatic analysis in Settings → Detection.
- **Trusted channels**: Add channels you trust to skip analysis.
- **Cache control**: Disable result caching in Settings → Privacy.
- **Uninstall**: Removing the extension deletes all local data.

## Children's Privacy

This extension does not knowingly collect any information from children under 13. The extension processes only publicly visible YouTube video metadata.

## Changes to This Policy

Material changes will be noted in the extension's changelog and version update notes. Continued use after changes constitutes acceptance.

## Contact

For privacy questions, contact: **beautifulplanet** via the extension's support page on the Chrome Web Store.
