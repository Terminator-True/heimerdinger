import { describe, it, expect } from 'vitest'
import { validateCount, DEFAULT_COUNT, MIN_COUNT, MAX_COUNT } from './LandingView'

describe('validateCount', () => {
  it('returns the default when blank', () => {
    expect(validateCount('')).toBe(DEFAULT_COUNT)
    expect(validateCount('   ')).toBe(DEFAULT_COUNT)
  })

  it('accepts in-bounds values', () => {
    expect(validateCount('1')).toBe(1)
    expect(validateCount('100')).toBe(100)
    expect(validateCount('42')).toBe(42)
    expect(validateCount(' 7 ')).toBe(7)
  })

  it('blocks out-of-bounds and non-numeric input without a value', () => {
    expect(validateCount('0')).toEqual({ error: 'La cantidad debe estar entre 1 y 100.' })
    expect(validateCount('101')).toEqual({ error: 'La cantidad debe estar entre 1 y 100.' })
    expect(validateCount('-5')).toEqual({ error: 'La cantidad debe estar entre 1 y 100.' })
    expect(validateCount('abc')).toEqual({ error: 'Ingresá un número entre 1 y 100.' })
    // Bounds are exactly enforced:
    expect(validateCount(String(MIN_COUNT - 1))).toHaveProperty('error')
    expect(validateCount(String(MAX_COUNT + 1))).toHaveProperty('error')
  })
})
