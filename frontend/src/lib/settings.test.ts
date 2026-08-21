import { afterEach, describe, it, expect, vi } from 'vitest'
import { getApiKey, saveApiKey, getBaseUrl, setBaseUrl } from './settings'

describe('settings', () => {
  afterEach(() => {
    localStorage.removeItem('heimerdinger.apiKey')
    localStorage.removeItem('heimerdinger.baseUrl')
  })

  it('returns empty api key when nothing stored', () => {
    expect(getApiKey()).toBe('')
  })

  it('round-trips an api key through localStorage', () => {
    saveApiKey('secret-key-123')
    expect(localStorage.getItem('heimerdinger.apiKey')).toBe('secret-key-123')
    expect(getApiKey()).toBe('secret-key-123')
  })

  it('clears the stored key when set to empty string', () => {
    saveApiKey('k')
    saveApiKey('')
    expect(localStorage.getItem('heimerdinger.apiKey')).toBeNull()
    expect(getApiKey()).toBe('')
  })

  it('defaults baseUrl to http://localhost:8000', () => {
    expect(getBaseUrl()).toBe('http://localhost:8000')
  })

  it('returns a stored baseUrl override instead of the default', () => {
    setBaseUrl('http://192.168.1.50:8000')
    expect(getBaseUrl()).toBe('http://192.168.1.50:8000')
    expect(localStorage.getItem('heimerdinger.baseUrl')).toBe(
      'http://192.168.1.50:8000',
    )
  })

  it('falls back to the default when the stored value is removed externally', () => {
    setBaseUrl('http://example.com')
    localStorage.removeItem('heimerdinger.baseUrl')
    expect(getBaseUrl()).toBe('http://localhost:8000')
  })

  it('reports failure instead of crashing when storage writes throw', () => {
    vi.stubGlobal(
      'localStorage',
      {
        getItem: () => null,
        removeItem: () => {},
        setItem: () => {
          throw new DOMException('quota exceeded', 'QuotaExceededError')
        },
      },
    )
    try {
      expect(saveApiKey('secret-key')).toBe(false)
      expect(getApiKey()).toBe('')
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
