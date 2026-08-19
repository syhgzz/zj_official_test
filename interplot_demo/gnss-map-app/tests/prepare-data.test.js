import { afterEach, describe, expect, test } from 'vitest'
import { mkdtemp, readFile, rm, utimes, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'

import { findLatestGnssResponse, prepareData } from '../scripts/prepare-data.mjs'

const temporaryDirectories = []

function responseFixture(stations, overrides = {}) {
  return {
    number: '3.6.2',
    title: '卫星模块: 站点列表及状态（全部）',
    path: '/api/v1/gnss-device/stations',
    request_params: { pageNum: '1-36', pageSize: 100 },
    response: {
      code: 200,
      data: {
        total: stations.length,
        fetchedPageCount: 36,
        uniqueStationCount: stations.length,
        duplicateStationCodeCount: 0,
        stations,
      },
    },
    ...overrides,
  }
}

async function makeTempDirectory() {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'gnss-map-test-'))
  temporaryDirectories.push(directory)
  return directory
}

afterEach(async () => {
  await Promise.all(temporaryDirectories.splice(0).map(directory => rm(directory, { recursive: true, force: true })))
})

describe('findLatestGnssResponse', () => {
  test('selects the newest valid merged GNSS response and ignores unrelated JSON', async () => {
    const directory = await makeTempDirectory()
    const older = path.join(directory, 'old-valid.json')
    const newer = path.join(directory, 'new-valid.json')
    const unrelated = path.join(directory, 'newer-unrelated.json')
    await writeFile(older, JSON.stringify(responseFixture([{ stationCode: 'OLD' }])))
    await writeFile(newer, JSON.stringify(responseFixture([{ stationCode: 'NEW' }])))
    await writeFile(unrelated, JSON.stringify(responseFixture([], { path: '/api/v1/other' })))

    const base = new Date('2026-08-19T00:00:00Z')
    await utimes(older, base, base)
    await utimes(newer, new Date(base.getTime() + 1_000), new Date(base.getTime() + 1_000))
    await utimes(unrelated, new Date(base.getTime() + 2_000), new Date(base.getTime() + 2_000))

    const selected = await findLatestGnssResponse(directory)

    expect(path.basename(selected)).toBe('new-valid.json')
  })
})

describe('prepareData', () => {
  test('writes a compact browser payload without the request wrapper', async () => {
    const directory = await makeTempDirectory()
    const outputFile = path.join(directory, 'public', 'gnss-stations.json')
    const stations = [{ stationCode: 'A' }, { stationCode: 'B' }]
    await writeFile(path.join(directory, 'source.json'), JSON.stringify(responseFixture(stations)))

    const summary = await prepareData({ responsesDir: directory, outputFile })
    const output = JSON.parse(await readFile(outputFile, 'utf8'))

    expect(summary.stationCount).toBe(2)
    expect(output.meta.reportedTotal).toBe(2)
    expect(output.meta.fetchedPageCount).toBe(36)
    expect(output.meta.sourceFile).toBe('source.json')
    expect(output.stations).toEqual([{ stationCode: 'A' }, { stationCode: 'B' }])
    expect(output).not.toHaveProperty('request_params')
    expect(output).not.toHaveProperty('response')
  })
})
