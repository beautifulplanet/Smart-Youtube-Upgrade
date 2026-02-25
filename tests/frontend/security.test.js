/**
 * YouTube Safety Inspector — Frontend Unit Tests: security.test.js
 * Tests for API URL validation & endpoint allowlisting
 */
import { describe, it, expect } from 'vitest';
import { isAllowedApiUrl, isAllowedEndpoint, ALLOWED_ENDPOINTS } from './helpers.js';

// ─── isAllowedApiUrl ─────────────────────────────────────────

describe('isAllowedApiUrl', () => {
  // --- Accepted URLs ---
  it('allows localhost without port', () => {
    expect(isAllowedApiUrl('http://localhost')).toBe(true);
  });

  it('allows localhost with port 8000', () => {
    expect(isAllowedApiUrl('http://localhost:8000')).toBe(true);
  });

  it('allows localhost with HTTPS', () => {
    expect(isAllowedApiUrl('https://localhost:8000')).toBe(true);
  });

  it('allows 127.0.0.1 with port', () => {
    expect(isAllowedApiUrl('http://127.0.0.1:8000')).toBe(true);
  });

  it('allows 127.0.0.1 without port', () => {
    expect(isAllowedApiUrl('http://127.0.0.1')).toBe(true);
  });

  it('allows beautifulplanet.dev subdomain', () => {
    expect(isAllowedApiUrl('https://api.beautifulplanet.dev')).toBe(true);
  });

  it('allows nested beautifulplanet.dev subdomain', () => {
    expect(isAllowedApiUrl('https://staging-api.beautifulplanet.dev')).toBe(true);
  });

  // --- Rejected URLs ---
  it('rejects arbitrary external URL', () => {
    expect(isAllowedApiUrl('https://evil.example.com')).toBe(false);
  });

  it('rejects localhost with trailing path', () => {
    // The regex anchors with $, so a path after the port should fail
    expect(isAllowedApiUrl('http://localhost:8000/api')).toBe(false);
  });

  it('rejects javascript: protocol', () => {
    expect(isAllowedApiUrl('javascript:alert(1)')).toBe(false);
  });

  it('rejects data: URI', () => {
    expect(isAllowedApiUrl('data:text/html,<h1>hi</h1>')).toBe(false);
  });

  it('rejects empty string', () => {
    expect(isAllowedApiUrl('')).toBe(false);
  });

  it('rejects beautifulplanet.dev over HTTP (requires HTTPS)', () => {
    expect(isAllowedApiUrl('http://api.beautifulplanet.dev')).toBe(false);
  });

  it('rejects look-alike domain', () => {
    expect(isAllowedApiUrl('https://beautifulplanet.dev.evil.com')).toBe(false);
  });

  it('rejects port injection', () => {
    expect(isAllowedApiUrl('http://localhost:8000@evil.com')).toBe(false);
  });

  it('rejects file protocol', () => {
    expect(isAllowedApiUrl('file:///etc/passwd')).toBe(false);
  });
});

// ─── isAllowedEndpoint ───────────────────────────────────────

describe('isAllowedEndpoint', () => {
  it('allows /analyze', () => {
    expect(isAllowedEndpoint('/analyze')).toBe(true);
  });

  it('allows /health', () => {
    expect(isAllowedEndpoint('/health')).toBe(true);
  });

  it('allows /analyze with query string', () => {
    expect(isAllowedEndpoint('/analyze?video_id=abc')).toBe(true);
  });

  it('allows /real-alternatives', () => {
    expect(isAllowedEndpoint('/real-alternatives')).toBe(true);
  });

  it('allows /ai-tutorials', () => {
    expect(isAllowedEndpoint('/ai-tutorials')).toBe(true);
  });

  it('allows /ai-entertainment', () => {
    expect(isAllowedEndpoint('/ai-entertainment')).toBe(true);
  });

  it('allows /signatures', () => {
    expect(isAllowedEndpoint('/signatures')).toBe(true);
  });

  it('allows /categories', () => {
    expect(isAllowedEndpoint('/categories')).toBe(true);
  });

  it('rejects unknown endpoint', () => {
    expect(isAllowedEndpoint('/admin')).toBe(false);
  });

  it('rejects path traversal', () => {
    expect(isAllowedEndpoint('/analyze/../admin')).toBe(false);
  });

  it('rejects empty string', () => {
    expect(isAllowedEndpoint('')).toBe(false);
  });

  it('rejects root path', () => {
    expect(isAllowedEndpoint('/')).toBe(false);
  });

  it('validates ALLOWED_ENDPOINTS list has 7 entries', () => {
    expect(ALLOWED_ENDPOINTS).toHaveLength(7);
  });
});
