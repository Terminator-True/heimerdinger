import { describe, expect, it } from 'vitest'
import { goldEarnedSeries, goldEfficiency } from './gold'

describe('goldEfficiency badge hide-logic', () => {
  it('returns ratio when both goldEarned and gold_value are present', () => {
    expect(goldEfficiency({ goldEarned: 100, items: { gold_value: 200 } })).toBe(0.5)
  })

  it('returns null when gold_value is 0 (unknown) — badge hidden', () => {
    expect(goldEfficiency({ goldEarned: 100, items: { gold_value: 0 } })).toBeNull()
  })

  it('returns null when goldEarned is absent after parsing', () => {
    expect(goldEfficiency({ items: { gold_value: 200 } })).toBeNull()
    expect(goldEfficiency({ goldEarned: null, items: { gold_value: 200 } })).toBeNull()
  })

  it('returns null when items/gold_value is absent after parsing', () => {
    expect(goldEfficiency({ goldEarned: 100 })).toBeNull()
    expect(goldEfficiency({ goldEarned: 100, items: {} })).toBeNull()
    expect(goldEfficiency({ goldEarned: 100, items: { gold_value: null } })).toBeNull()
  })
})

describe('goldEarnedSeries flat-key chart mapping', () => {
  it('maps mean/median/p25/p75 from the flat keys', () => {
    const series = goldEarnedSeries({
      goldEarned: 100,
      goldEarned_median: 90,
      goldEarned_p25: 70,
      goldEarned_p75: 120,
    })
    expect(series).toEqual([
      { label: 'Media', value: 100 },
      { label: 'Mediana', value: 90 },
      { label: 'P25', value: 70 },
      { label: 'P75', value: 120 },
    ])
  })

  it('skips omitted and null metrics entirely', () => {
    const series = goldEarnedSeries({
      goldEarned: 100,
      goldEarned_median: null,
      // p25/p75 omitted (no samples)
    })
    expect(series).toEqual([{ label: 'Media', value: 100 }])
  })

  it('returns empty array when the metric is fully absent', () => {
    expect(goldEarnedSeries({})).toEqual([])
  })
})
