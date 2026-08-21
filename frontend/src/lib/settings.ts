// Runtime-only app settings. The API key MUST never come from import.meta.env:
// env values are baked into the bundle at build time and would ship the key
// to every visitor. localStorage keeps it device-local.

const API_KEY_STORAGE = 'heimerdinger.apiKey'
const BASE_URL_STORAGE = 'heimerdinger.baseUrl'
export const DEFAULT_BASE_URL = 'http://localhost:8000'

function read(key: string): string {
  return localStorage.getItem(key) ?? ''
}

function write(key: string, value: string): boolean {
  try {
    if (value === '') {
      localStorage.removeItem(key)
    } else {
      localStorage.setItem(key, value)
    }
    return true
  } catch {
    // QuotaExceededError / SecurityError (private mode, full storage):
    // surface failure instead of crashing the dialog's save path.
    return false
  }
}

export function getApiKey(): string {
  return read(API_KEY_STORAGE)
}

export function saveApiKey(key: string): boolean {
  return write(API_KEY_STORAGE, key.trim())
}

export function getBaseUrl(): string {
  const stored = read(BASE_URL_STORAGE)
  return stored === '' ? DEFAULT_BASE_URL : stored
}

export function setBaseUrl(url: string): boolean {
  return write(BASE_URL_STORAGE, url.trim())
}
