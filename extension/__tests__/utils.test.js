/**
 * YouTube Safety Inspector — Frontend Unit Tests: utils.js
 * Tests for pure utility functions extracted from content/utils.js
 */
import { describe, it, expect } from 'vitest';
import { getVideoId, escapeHtml } from './helpers.js';

// ─── getVideoId ──────────────────────────────────────────────

describe('getVideoId', () => {
  // --- Regular watch URLs ---
  it('extracts ID from standard watch URL', () => {
    expect(getVideoId('https://www.youtube.com/watch?v=dQw4w9WgXcQ'))
      .toBe('dQw4w9WgXcQ');
  });

  it('extracts ID when v= is not the first param', () => {
    expect(getVideoId('https://www.youtube.com/watch?feature=share&v=dQw4w9WgXcQ'))
      .toBe('dQw4w9WgXcQ');
  });

  it('extracts ID with trailing params', () => {
    expect(getVideoId('https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120'))
      .toBe('dQw4w9WgXcQ');
  });

  it('handles URL with only v param', () => {
    expect(getVideoId('https://youtube.com/watch?v=abcABC_-012'))
      .toBe('abcABC_-012');
  });

  // --- Shorts URLs ---
  it('extracts ID from Shorts URL', () => {
    expect(getVideoId('https://www.youtube.com/shorts/dQw4w9WgXcQ'))
      .toBe('dQw4w9WgXcQ');
  });

  it('extracts ID from Shorts URL with trailing slash', () => {
    expect(getVideoId('https://www.youtube.com/shorts/dQw4w9WgXcQ/'))
      .toBe('dQw4w9WgXcQ');
  });

  it('extracts ID from Shorts URL with query params', () => {
    expect(getVideoId('https://www.youtube.com/shorts/dQw4w9WgXcQ?feature=share'))
      .toBe('dQw4w9WgXcQ');
  });

  // --- Edge cases ---
  it('returns null for YouTube homepage', () => {
    expect(getVideoId('https://www.youtube.com/')).toBeNull();
  });

  it('returns null for channel page', () => {
    expect(getVideoId('https://www.youtube.com/channel/UCxxxxxx')).toBeNull();
  });

  it('returns null for search page', () => {
    expect(getVideoId('https://www.youtube.com/results?search_query=test')).toBeNull();
  });

  it('returns null when ID is too short', () => {
    expect(getVideoId('https://www.youtube.com/watch?v=abc')).toBeNull();
  });

  it('returns null when ID is too long', () => {
    expect(getVideoId('https://www.youtube.com/watch?v=dQw4w9WgXcQ_extra')).toBeNull();
  });

  it('returns null for empty string', () => {
    expect(getVideoId('')).toBeNull();
  });

  it('returns null for non-YouTube URL', () => {
    expect(getVideoId('https://vimeo.com/12345')).toBeNull();
  });

  // --- Security: reject injected IDs ---
  it('rejects ID with special characters', () => {
    expect(getVideoId('https://www.youtube.com/watch?v=<script>aler')).toBeNull();
  });

  it('rejects ID with spaces', () => {
    expect(getVideoId('https://www.youtube.com/watch?v=abc def ghi')).toBeNull();
  });
});

// ─── escapeHtml ──────────────────────────────────────────────

describe('escapeHtml', () => {
  it('escapes ampersand', () => {
    expect(escapeHtml('a & b')).toBe('a &amp; b');
  });

  it('escapes less-than', () => {
    expect(escapeHtml('<script>')).toBe('&lt;script&gt;');
  });

  it('escapes greater-than', () => {
    expect(escapeHtml('1 > 0')).toBe('1 &gt; 0');
  });

  it('escapes double quotes', () => {
    expect(escapeHtml('"hello"')).toBe('&quot;hello&quot;');
  });

  it('escapes single quotes', () => {
    expect(escapeHtml("it's")).toBe('it&#39;s');
  });

  it('escapes all special chars at once', () => {
    expect(escapeHtml('<div class="x">&\'</div>'))
      .toBe('&lt;div class=&quot;x&quot;&gt;&amp;&#39;&lt;/div&gt;');
  });

  it('returns empty string for null', () => {
    expect(escapeHtml(null)).toBe('');
  });

  it('returns empty string for undefined', () => {
    expect(escapeHtml(undefined)).toBe('');
  });

  it('returns empty string for empty input', () => {
    expect(escapeHtml('')).toBe('');
  });

  it('leaves safe text unchanged', () => {
    expect(escapeHtml('Hello World 123')).toBe('Hello World 123');
  });

  it('coerces numbers to string', () => {
    expect(escapeHtml(42)).toBe('42');
  });

  // XSS payloads
  it('neutralises script injection', () => {
    const payload = '<img src=x onerror="alert(1)">';
    const escaped = escapeHtml(payload);
    expect(escaped).not.toContain('<img');
    // The word "onerror" survives as text, but it's harmless because
    // the surrounding < > " are all escaped, so no tag is created.
    expect(escaped).toContain('&lt;img');
    expect(escaped).toContain('&quot;');
  });

  it('neutralises event handler injection', () => {
    const payload = '" onmouseover="alert(document.cookie)"';
    const result = escapeHtml(payload);
    expect(result).not.toContain('" onmouseover');
  });
});
