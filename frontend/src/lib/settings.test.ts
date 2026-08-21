import { describe, it, expect } from 'vitest'
import { getApiKey, setApiKey, getBaseUrl, setBaseUrl } from './settings'

describe('settings', () => {
  it('returns empty api key when nothing stored', () => {
    expect(getApiKey()).toBe('')
  })

  it('round-trips an api key through localStorage', () => {
    setApiKey('secret-key-123')
    expect(localStorage.getItem('heimerdinger.apiKey')).toBe('secret-key-123')
    expect(getApiKey()).toBe('secret-key-123')
  })

  it('clears the stored key when set to empty string', () => {
    setApiKey('k')
    setApiKey('')
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
})
