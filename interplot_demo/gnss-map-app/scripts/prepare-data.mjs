import { mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const GNSS_PATH = '/api/v1/gnss-device/stations'
const MERGED_PAGE_RANGE = '1-36'

async function readValidCandidate(filePath) {
  try {
    const payload = JSON.parse(await readFile(filePath, 'utf8'))
    const pageNum = String(payload?.request_params?.pageNum ?? '')
    if (
      payload?.path !== GNSS_PATH
      || pageNum !== MERGED_PAGE_RANGE
      || !Array.isArray(payload?.response?.data?.stations)
    ) {
      return null
    }
    return payload
  } catch {
    return null
  }
}

export async function findLatestGnssResponse(responsesDir) {
  let entries
  try {
    entries = await readdir(responsesDir, { withFileTypes: true })
  } catch (error) {
    throw new Error(`无法读取响应目录 ${responsesDir}: ${error.message}`)
  }

  const candidates = []
  for (const entry of entries) {
    if (!entry.isFile() || path.extname(entry.name).toLowerCase() !== '.json') continue
    const filePath = path.join(responsesDir, entry.name)
    const payload = await readValidCandidate(filePath)
    if (!payload) continue
    const fileStat = await stat(filePath)
    candidates.push({ filePath, mtimeMs: fileStat.mtimeMs })
  }

  if (candidates.length === 0) {
    throw new Error(`未在 ${responsesDir} 找到页码范围为 ${MERGED_PAGE_RANGE} 的 GNSS 合并响应`)
  }

  candidates.sort((left, right) => right.mtimeMs - left.mtimeMs)
  return candidates[0].filePath
}

export async function prepareData({ responsesDir, outputFile }) {
  const sourceFile = await findLatestGnssResponse(responsesDir)
  const source = JSON.parse(await readFile(sourceFile, 'utf8'))
  const data = source.response.data
  const stations = data.stations
  const output = {
    meta: {
      sourceFile: path.basename(sourceFile),
      reportedTotal: Number(data.total) || stations.length,
      fetchedPageCount: Number(data.fetchedPageCount) || 36,
      uniqueStationCount: Number(data.uniqueStationCount) || null,
      duplicateStationCodeCount: Number(data.duplicateStationCodeCount) || 0,
      preparedAt: new Date().toISOString(),
    },
    stations,
  }

  await mkdir(path.dirname(outputFile), { recursive: true })
  await writeFile(outputFile, JSON.stringify(output), 'utf8')

  return {
    sourceFile,
    stationCount: stations.length,
    outputFile,
  }
}

const scriptFile = fileURLToPath(import.meta.url)
const scriptDirectory = path.dirname(scriptFile)

if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) {
  const responsesDir = path.resolve(scriptDirectory, '../../../responses')
  const outputFile = path.resolve(scriptDirectory, '../public/data/gnss-stations.json')
  try {
    const result = await prepareData({ responsesDir, outputFile })
    console.log(`GNSS 数据已准备：${path.basename(result.sourceFile)}，${result.stationCount} 条记录`)
    console.log(`浏览器数据：${result.outputFile}`)
  } catch (error) {
    console.error(`GNSS 数据准备失败：${error.message}`)
    process.exitCode = 1
  }
}
