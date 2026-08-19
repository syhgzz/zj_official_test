import { describe, expect, test, vi } from 'vitest'

import {
  createStationLayer,
  extractStationFromLayerEvent,
} from '../src/map/createStationLayer.js'

class FakeLabelMarker {
  constructor(options) {
    this.options = options
  }

  getExtData() {
    return this.options.extData
  }
}

class FakeLabelsLayer {
  constructor(options) {
    this.options = options
    this.markers = []
    this.listeners = new Map()
    this.show = vi.fn()
    this.hide = vi.fn()
  }

  add(markers) {
    this.markers.push(...markers)
  }

  on(eventName, callback) {
    this.listeners.set(eventName, callback)
  }

  off(eventName, callback) {
    if (this.listeners.get(eventName) === callback) this.listeners.delete(eventName)
  }

  emit(eventName, event) {
    this.listeners.get(eventName)?.(event)
  }
}

function fakeAmap() {
  return {
    LabelMarker: FakeLabelMarker,
    LabelsLayer: FakeLabelsLayer,
  }
}

function station(code, status = 'online') {
  return {
    stationCode: code,
    stationName: code,
    longitude: 106.58,
    latitude: 29.563,
    status,
  }
}

describe('extractStationFromLayerEvent', () => {
  test.each([
    { data: { data: { getExtData: () => station('nested') } } },
    { marker: { getExtData: () => station('marker') } },
    { target: { getExtData: () => station('target') } },
  ])('extracts extension data from supported AMap event shapes', event => {
    expect(extractStationFromLayerEvent(event).stationCode).toBeTruthy()
  })

  test('returns null for an event without station extension data', () => {
    expect(extractStationFromLayerEvent({ data: {} })).toBeNull()
  })
})

describe('createStationLayer', () => {
  test('adds all stations through one layer and one click listener', () => {
    const map = { add: vi.fn(), remove: vi.fn() }
    const onStationClick = vi.fn()
    const controller = createStationLayer({
      AMap: fakeAmap(),
      map,
      stations: [station('A'), station('B', 'offline'), station('C', 'unknown')],
      onStationClick,
    })

    expect(controller.markerCount).toBe(3)
    expect(controller.layer.markers).toHaveLength(3)
    expect(controller.layer.listeners.size).toBe(1)
    expect(controller.layer.options).toEqual({ zIndex: 300, collision: false })
    expect(map.add).toHaveBeenCalledOnce()
    expect(map.add).toHaveBeenCalledWith(controller.layer)

    controller.layer.emit('click', { marker: controller.layer.markers[1] })
    expect(onStationClick).toHaveBeenCalledWith(expect.objectContaining({ stationCode: 'B' }))
  })

  test('toggles visibility and removes listeners and map layer on destroy', () => {
    const map = { add: vi.fn(), remove: vi.fn() }
    const controller = createStationLayer({
      AMap: fakeAmap(),
      map,
      stations: [station('A')],
      onStationClick: vi.fn(),
    })

    controller.setVisible(false)
    controller.setVisible(true)
    controller.destroy()

    expect(controller.layer.hide).toHaveBeenCalledOnce()
    expect(controller.layer.show).toHaveBeenCalledOnce()
    expect(controller.layer.listeners.size).toBe(0)
    expect(map.remove).toHaveBeenCalledWith(controller.layer)
  })
})
