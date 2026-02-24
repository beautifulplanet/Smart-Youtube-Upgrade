# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 3.0.x   | :white_check_mark: |
| 2.1.x   | :white_check_mark: |
| < 2.0   | :x:                |

## Security Measures

### Input Validation
- All YouTube video IDs validated with regex: `^[a-zA-Z0-9_-]{11}$`
- Prevents injection attacks in API endpoints and subprocess calls

### XSS Protection
- All user-generated content escaped with `escapeHtml()`
- URLs validated to only allow YouTube domains before rendering
- Content Security Policy enforced in extension manifest

### Rate Limiting
- 30-second cooldown per video analysis
- 100 videos per day per user limit
- Server-side API quota enforcement (10,000 daily limit)

### Security Headers
All API responses include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`

### Dependencies
- All Python dependencies pinned to exact versions
- Regular security audits recommended

## Development vs Production

### Development (localhost)
The extension includes `http://localhost:8000/*` in host_permissions for local development. This is:
- ✅ Safe for local testing
- ✅ Required for development workflow
- ⚠️ Should NOT be used in production

### Production Deployment
For Chrome Web Store or production deployment:

1. Deploy backend with HTTPS (required)
2. Update API URL via Chrome storage:
   ```javascript
   chrome.storage.sync.set({ apiBaseUrl: 'https://your-api.example.com' });
   ```
3. Consider removing localhost permissions from manifest

## Reporting a Vulnerability

If you discover a security vulnerability:

1. **Do NOT** open a public GitHub issue
2. Use [GitHub Security Advisories](https://github.com/beautifulplanet/youtube-safety-inspector/security/advisories/new) to report privately
3. Alternatively, open a private vulnerability report via GitHub's "Report a vulnerability" button
4. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work to patch critical issues within 7 days.

## Security Checklist for Contributors

Before submitting PRs:
- [ ] No hardcoded API keys or secrets
- [ ] All user input validated/escaped
- [ ] No `eval()` or `innerHTML` with unsanitized data
- [ ] Dependencies from trusted sources only
- [ ] Tested with malformed inputs
