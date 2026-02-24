/**
 * YouTube Safety Inspector — Frontend Unit Tests: settings.test.js
 * Tests for DEFAULT_SETTINGS integrity and shape
 */
import { describe, it, expect } from 'vitest';
import { DEFAULT_SETTINGS } from './helpers.js';

describe('DEFAULT_SETTINGS', () => {
  // --- Shape ---
  it('is an object', () => {
    expect(typeof DEFAULT_SETTINGS).toBe('object');
    expect(DEFAULT_SETTINGS).not.toBeNull();
  });

  it('has all expected keys', () => {
    const required = [
      'enableAIDetection', 'autoAnalyze',
      'enableRegularVideos', 'enableShorts',
      'enableAlternatives', 'enableAITutorials', 'enableAIEntertainment',
      'bannerStyle', 'autoDismiss',
      'enableReminders', 'enableEndAlert',
      'enableSound', 'enableVisualEffects',
      'aiSensitivity', 'safetySensitivity',
      'enableCache',
      'trustedChannels',
    ];
    for (const key of required) {
      expect(DEFAULT_SETTINGS).toHaveProperty(key);
    }
  });

  // --- Defaults are sensible ---
  it('enables AI detection by default', () => {
    expect(DEFAULT_SETTINGS.enableAIDetection).toBe(true);
  });

  it('enables auto-analyze by default', () => {
    expect(DEFAULT_SETTINGS.autoAnalyze).toBe(true);
  });

  it('disables sound by default', () => {
    expect(DEFAULT_SETTINGS.enableSound).toBe(false);
  });

  it('uses modal banner style', () => {
    expect(DEFAULT_SETTINGS.bannerStyle).toBe('modal');
  });

  it('has autoDismiss of 0 (never)', () => {
    expect(DEFAULT_SETTINGS.autoDismiss).toBe(0);
  });

  it('sets sensitivity levels to medium', () => {
    expect(DEFAULT_SETTINGS.aiSensitivity).toBe('medium');
    expect(DEFAULT_SETTINGS.safetySensitivity).toBe('medium');
  });

  it('enables cache by default', () => {
    expect(DEFAULT_SETTINGS.enableCache).toBe(true);
  });

  // --- Trusted channels ---
  it('trustedChannels is an array', () => {
    expect(Array.isArray(DEFAULT_SETTINGS.trustedChannels)).toBe(true);
  });

  it('trustedChannels has at least 5 entries', () => {
    expect(DEFAULT_SETTINGS.trustedChannels.length).toBeGreaterThanOrEqual(5);
  });

  it('trustedChannels contains known safe channels', () => {
    expect(DEFAULT_SETTINGS.trustedChannels).toContain('National Geographic');
    expect(DEFAULT_SETTINGS.trustedChannels).toContain('BBC Earth');
    expect(DEFAULT_SETTINGS.trustedChannels).toContain('PBS Nature');
  });

  it('trustedChannels entries are all non-empty strings', () => {
    for (const ch of DEFAULT_SETTINGS.trustedChannels) {
      expect(typeof ch).toBe('string');
      expect(ch.trim().length).toBeGreaterThan(0);
    }
  });

  // --- Boolean fields are indeed booleans ---
  it('all toggle fields are booleans', () => {
    const booleanFields = [
      'enableAIDetection', 'autoAnalyze',
      'enableRegularVideos', 'enableShorts',
      'enableAlternatives', 'enableAITutorials', 'enableAIEntertainment',
      'enableReminders', 'enableEndAlert',
      'enableSound', 'enableVisualEffects',
      'enableCache',
    ];
    for (const field of booleanFields) {
      expect(typeof DEFAULT_SETTINGS[field]).toBe('boolean');
    }
  });

  // --- Sensitivity enum check ---
  it('sensitivity values are one of low/medium/high', () => {
    const valid = ['low', 'medium', 'high'];
    expect(valid).toContain(DEFAULT_SETTINGS.aiSensitivity);
    expect(valid).toContain(DEFAULT_SETTINGS.safetySensitivity);
  });
});
