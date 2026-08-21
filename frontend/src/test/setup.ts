import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// jsdom@30 exposes localStorage inconsistently under vitest; backfill a
// minimal in-memory Storage so tests exercise the same API surface.
if (typeof globalThis.localStorage === 'undefined') {
  const store = new Map<string, string>()
  const shim: Storage = {
    get length() {
      return store.size
    },
    clear: () => store.clear(),
    getItem: (k) => (store.has(k) ? store.get(k)! : null),
    key: (i) => Array.from(store.keys())[i] ?? null,
    removeItem: (k) => void store.delete(k),
    setItem: (k, v) => void store.set(k, String(v)),
  }
  Object.defineProperty(globalThis, 'localStorage', { value: shim })
}

afterEach(() => {
  cleanup()
  localStorage.clear()
})
