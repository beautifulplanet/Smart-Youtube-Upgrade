# Changelog

All notable changes to the YouTube Safety Inspector project.

## [2.1.0] - 2026-02-13

### Security
- Input validation on all API endpoints (video ID regex, Pydantic field limits)
- XSS prevention with `escapeHtml()` on all dynamic HTML rendering
- Server-side rate limiting per IP per endpoint (sliding window)
- Security headers middleware (X-Content-Type-Options, X-Frame-Options, etc.)
- Error responses no longer leak internal details to clients
- Content script restricted to YouTube domains via manifest
- Background script API proxy restricted to allowlisted endpoints only
- ReDoS prevention via input truncation before regex matching

### Added
- Async context manager for `YouTubeDataFetcher` (prevents resource leaks)
- Pre-compiled regex patterns for comment analysis (performance)
- Named constants replacing all magic numbers in analyzer and youtube_data
- Type hints on all public Python functions
- JSDoc comments on all frontend functions (27 functions documented)
- Python docstrings on all public methods
- Keyboard shortcuts: Esc (dismiss), I (toggle AI banner), Shift+A (analyze)
- WCAG accessibility: ARIA labels on all interactive elements, role attributes
- `prefers-reduced-motion` media query in both CSS files
- Persistent rate limiter (daily count survives browser restart via chrome.storage)
- pytest framework with 47 tests (58% coverage)
- Test coverage reporting via pytest-cov
- Integration tests for all API endpoints
- Unit tests for analyzer, youtube_data, and safety_db modules

### Changed
- URL change detection: replaced MutationObserver + setInterval with `yt-navigate-finish` + debounce
- All `print()` calls replaced with `logging` module
- All debug `console.log` statements removed from frontend (kept `console.error`)
- Version bumped to 2.1.0

### Fixed
- Dead code removed from analyzer.py (unused imports, unreachable branches)
- Duplicate `import httpx` in alternatives_finder.py
- Resource leak: YouTubeDataFetcher.close() not called on exceptions
- Rate limiter reset on browser restart (now persisted in chrome.storage)
- Redundant URL detection firing multiple times per navigation

### Removed
- MutationObserver-based URL detection (replaced by yt-navigate-finish)
- setInterval-based URL polling (replaced by event-driven approach)
- Debug console.log statements across all frontend files

## [2.0.0] - 2026-01-XX

### Added
- Initial release with Chrome extension and FastAPI backend
- Safety signature database with 25+ danger patterns
- AI content detection (title, description, comment, hashtag analysis)
- YouTube transcript analysis
- Safe alternative video suggestions
- Trusted channel allowlist
- Settings panel with export/import
