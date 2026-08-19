import { describe, expect, test } from 'vitest'

import {
  normalizeStation,
  normalizeStations,
  wgs84ToGcj02,
} from '../src/data/normalizeStations.js'

describe('wgs84ToGcj02', () => {
  test('leaves coordinates outside China unchanged', () => {
    expect(wgs84ToGcj02(2.3522, 48.8566)).toEqual([2.3522, 48.8566])
  })

  test('converts a Chongqing coordinate into the GCJ-02 map system', () => {
    const [longitude, latitude] = wgs84ToGcj02(106.58, 29.563)

    expect(longitude).toBeGreaterThan(106.58)
    expect(longitude).toBeLessThan(106.59)
    expect(latitude).toBeLessThan(29.563)
    expect(latitude).toBeGreaterThan(29.55)
  })
})

describe('normalizeStation', () => {
  test('rejects blank and out-of-range coordinates instead of converting them to zero', () => {
    expect(normalizeStation({ longitude: '', latitude: 29 }, 0)).toBeNull()
    expect(normalizeStation({ longitude: 106, latitude: null }, 1)).toBeNull()
    expect(normalizeStation({ longitude: 181, latitude: 29 }, 2)).toBeNull()
    expect(normalizeStation({ longitude: 106, latitude: -91 }, 3)).toBeNull()
  })

  test('normalizes station fields while preserving source coordinates', () => {
    const result = normalizeStation({
      stationCode: ' CQ-01 ',
      stationName: '重庆一号站',
      longitude: '106.58',
      latitude: '29.563',
      alt: '238.5',
      delay: '12.8',
      status: 'ONLINE',
      lastUpdateTime: '300',
      satelliteCount: { bdCount: 9 },
      signalQuality: { qualified: true, avgNoiseRatio: 42.1 },
    }, 7)

    expect(result).toMatchObject({
      id: 'CQ-01-7',
      stationCode: 'CQ-01',
      stationName: '重庆一号站',
      sourceLongitude: 106.58,
      sourceLatitude: 29.563,
      alt: 238.5,
      delay: 12.8,
      status: 'online',
      lastUpdateTime: 300,
      satelliteCount: { bdCount: 9 },
      signalQuality: { qualified: true, avgNoiseRatio: 42.1 },
    })
  })
})

describe('normalizeStations', () => {
  test('keeps raw rows and selects the newest highest-priority duplicate for unique mode', () => {
    const source = [
      { stationCode: 'A', longitude: 106.58, latitude: 29.563, status: 'offline', lastUpdateTime: 400 },
      { stationCode: 'A', longitude: 106.58, latitude: 29.563, status: 'online', lastUpdateTime: 100 },
      { stationCode: 'A', longitude: 106.58, latitude: 29.563, status: 'online', lastUpdateTime: 300 },
      { stationCode: 'B', longitude: 108.1, latitude: 30.2, status: 'paused', lastUpdateTime: 200 },
      { stationCode: 'INVALID', longitude: '', latitude: 31, status: 'online', lastUpdateTime: 500 },
    ]

    const result = normalizeStations(source, 5)

    expect(result.raw).toHaveLength(4)
    expect(result.unique).toHaveLength(2)
    expect(result.unique.find(item => item.stationCode === 'A').lastUpdateTime).toBe(300)
    expect(result.stats).toEqual({
      reportedTotal: 5,
      rawCount: 5,
      validCount: 4,
      uniqueCount: 2,
      duplicateCount: 2,
      invalidCoordinateCount: 1,
      onlineCount: 2,
      offlineCount: 1,
      unknownCount: 1,
    })
  })
})
