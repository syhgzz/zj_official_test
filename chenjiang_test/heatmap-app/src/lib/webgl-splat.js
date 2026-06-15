// webgl-splat.js — GPU-accelerated IDW / Gaussian interpolation via splatting
//
// Two-phase API — data uploaded ONCE, per-frame uniform-only updates:
//   state = splatInit(rawData, initOpts)    // upload lng/lat/value to GPU
//   {canvas, timings} = splatDraw(state, drawOpts)  // render per-frame
//
// Vertex shader converts lng/lat → pixel coords on GPU, zero CPU overhead.

// ---- helpers ----
function makeShader(gl, type, src) {
  const s = gl.createShader(type)
  gl.shaderSource(s, src)
  gl.compileShader(s)
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    console.warn('WebGL shader error:', gl.getShaderInfoLog(s))
    return null
  }
  return s
}

function createFloatTex(gl, iw, ih) {
  const t = gl.createTexture()
  gl.bindTexture(gl.TEXTURE_2D, t)
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, iw, ih, 0, gl.RGBA, gl.FLOAT, null)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
  return t
}

// ---- shaders (lng/lat → pixel conversion on GPU) ----
const SPLAT_VS = `#version 300 es
  in vec2 a_corner;
  in float a_lng;
  in float a_lat;
  in float a_value;
  uniform vec4 u_bounds;    // swLng, swLat, neLng, neLat
  uniform vec2 u_viewport;  // w, h
  uniform float u_gridStep;
  uniform vec2 u_scale;
  uniform float u_radius;
  out vec2 v_center;
  out float v_value;
  void main() {
    float nx = (a_lng - u_bounds.x) / (u_bounds.z - u_bounds.x);
    float ny = (a_lat - u_bounds.y) / (u_bounds.w - u_bounds.y);
    vec2 center = vec2(nx * u_viewport.x, (1.0 - ny) * u_viewport.y) / u_gridStep;
    vec2 offset = (a_corner - 0.5) * u_radius * 2.0;
    vec2 pos = (center + offset) * u_scale * 2.0 - 1.0;
    gl_Position = vec4(pos.x, -pos.y, 0.0, 1.0);
    v_center = center;
    v_value = a_value;
  }`

const SPLAT_FS = `#version 300 es
  precision highp float;
  in vec2 v_center; in float v_value;
  uniform float u_radius2; uniform float u_power; uniform float u_eps;
  uniform float u_sigma; uniform float u_h;
  layout(location = 0) out vec4 outWVal;
  layout(location = 1) out vec4 outW;
  void main() {
    float dy = gl_FragCoord.y - (u_h - v_center.y);
    float d2 = (gl_FragCoord.x - v_center.x) * (gl_FragCoord.x - v_center.x) + dy * dy;
    if (d2 > u_radius2) discard;
    float w = u_sigma > 0.0
      ? exp(d2 * (-0.5 / (u_sigma * u_sigma)))
      : 1.0 / pow(d2 + u_eps, u_power * 0.5);
    outWVal = vec4(w * v_value, 0.0, 0.0, 1.0);
    outW = vec4(w, 0.0, 0.0, 1.0);
  }`

const COMP_VS = `#version 300 es
  in vec2 a_pos;
  out vec2 v_uv;
  void main() {
    gl_Position = vec4(a_pos, 0.0, 1.0);
    v_uv = a_pos * 0.5 + 0.5;
  }`

const COMP_FS = `#version 300 es
  precision highp float;
  in vec2 v_uv;
  uniform sampler2D u_texWVal;
  uniform sampler2D u_texW;
  uniform sampler2D u_lut;
  uniform float u_vMin;
  uniform float u_vRange;
  uniform float u_opacity;
  out vec4 outColor;
  void main() {
    float wv = texture(u_texWVal, v_uv).r;
    float w  = texture(u_texW, v_uv).r;
    if (w <= 0.0) discard;
    float val = wv / w;
    float t = clamp((val - u_vMin) / u_vRange, 0.0, 1.0);
    vec4 c = texture(u_lut, vec2(t, 0.5));
    outColor = vec4(c.rgb, c.a * u_opacity);
  }`

// ======== splatInit: one-time setup, upload data to GPU ========
export function splatInit(rawArrays, options) {
  const {
    colorLut, valueMin, valueMax,
    idwPower = 2, idwEpsilon = 0.1, opacity = 0.7
  } = options
  const { rawLng, rawLat, rawVal } = rawArrays
  if (!rawLng || !rawLng.length) return null
  const n = rawLng.length

  const canvas = new OffscreenCanvas(1, 1)
  const gl = canvas.getContext('webgl2', {
    antialias: false, depth: false, stencil: false,
    preserveDrawingBuffer: true, premultipliedAlpha: false
  })
  if (!gl) return null
  if (!gl.getExtension('EXT_color_buffer_float')) return null

  // Compile shaders & link programs (once)
  const vs1 = makeShader(gl, gl.VERTEX_SHADER, SPLAT_VS)
  const fs1 = makeShader(gl, gl.FRAGMENT_SHADER, SPLAT_FS)
  if (!vs1 || !fs1) return null
  const prog1 = gl.createProgram()
  gl.attachShader(prog1, vs1); gl.attachShader(prog1, fs1)
  gl.linkProgram(prog1)
  if (!gl.getProgramParameter(prog1, gl.LINK_STATUS)) return null

  const vs2 = makeShader(gl, gl.VERTEX_SHADER, COMP_VS)
  const fs2 = makeShader(gl, gl.FRAGMENT_SHADER, COMP_FS)
  if (!vs2 || !fs2) return null
  const prog2 = gl.createProgram()
  gl.attachShader(prog2, vs2); gl.attachShader(prog2, fs2)
  gl.linkProgram(prog2)
  if (!gl.getProgramParameter(prog2, gl.LINK_STATUS)) return null

  // Static geometry
  const quadVerts = new Float32Array([0,0, 1,0, 1,1, 0,0, 1,1, 0,1])
  const quadBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf)
  gl.bufferData(gl.ARRAY_BUFFER, quadVerts, gl.STATIC_DRAW)

  const fsQuad = new Float32Array([-1,-1, 1,-1, 1,1, -1,-1, 1,1, -1,1])
  const fsBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, fsBuf)
  gl.bufferData(gl.ARRAY_BUFFER, fsQuad, gl.STATIC_DRAW)

  // LUT texture (constant)
  const lutTex = gl.createTexture()
  gl.bindTexture(gl.TEXTURE_2D, lutTex)
  const rgbaLut = new Uint8Array(256 * 4)
  for (let i = 0; i < 256; i++) {
    rgbaLut[i * 4] = colorLut[i * 4]
    rgbaLut[i * 4 + 1] = colorLut[i * 4 + 1]
    rgbaLut[i * 4 + 2] = colorLut[i * 4 + 2]
    rgbaLut[i * 4 + 3] = colorLut[i * 4 + 3]
  }
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 256, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, rgbaLut)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)

  // Upload instance data (raw lng/lat/value as Float32Arrays) — stays on GPU forever
  const lngBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, lngBuf)
  gl.bufferData(gl.ARRAY_BUFFER, rawLng, gl.STATIC_DRAW)

  const latBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, latBuf)
  gl.bufferData(gl.ARRAY_BUFFER, rawLat, gl.STATIC_DRAW)

  const valueBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, valueBuf)
  gl.bufferData(gl.ARRAY_BUFFER, rawVal, gl.STATIC_DRAW)

  // Bind constant attribs + uniforms
  gl.useProgram(prog1)
  gl.uniform1f(gl.getUniformLocation(prog1, 'u_power'), idwPower)
  gl.uniform1f(gl.getUniformLocation(prog1, 'u_eps'), idwEpsilon)
  const aCornerLoc = gl.getAttribLocation(prog1, 'a_corner')
  gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf)
  gl.enableVertexAttribArray(aCornerLoc)
  gl.vertexAttribPointer(aCornerLoc, 2, gl.FLOAT, false, 0, 0)
  const aLngLoc = gl.getAttribLocation(prog1, 'a_lng')
  gl.bindBuffer(gl.ARRAY_BUFFER, lngBuf)
  gl.enableVertexAttribArray(aLngLoc)
  gl.vertexAttribPointer(aLngLoc, 1, gl.FLOAT, false, 0, 0)
  gl.vertexAttribDivisor(aLngLoc, 1)

  const aLatLoc = gl.getAttribLocation(prog1, 'a_lat')
  gl.bindBuffer(gl.ARRAY_BUFFER, latBuf)
  gl.enableVertexAttribArray(aLatLoc)
  gl.vertexAttribPointer(aLatLoc, 1, gl.FLOAT, false, 0, 0)
  gl.vertexAttribDivisor(aLatLoc, 1)

  const aValueLoc = gl.getAttribLocation(prog1, 'a_value')
  gl.bindBuffer(gl.ARRAY_BUFFER, valueBuf)
  gl.enableVertexAttribArray(aValueLoc)
  gl.vertexAttribPointer(aValueLoc, 1, gl.FLOAT, false, 0, 0)
  gl.vertexAttribDivisor(aValueLoc, 1)

  gl.useProgram(prog2)
  gl.uniform1i(gl.getUniformLocation(prog2, 'u_texWVal'), 0)
  gl.uniform1i(gl.getUniformLocation(prog2, 'u_texW'), 1)
  gl.uniform1i(gl.getUniformLocation(prog2, 'u_lut'), 2)
  gl.uniform1f(gl.getUniformLocation(prog2, 'u_vMin'), valueMin)
  gl.uniform1f(gl.getUniformLocation(prog2, 'u_vRange'), valueMax - valueMin || 1.0)
  gl.uniform1f(gl.getUniformLocation(prog2, 'u_opacity'), opacity)
  const aPosLoc = gl.getAttribLocation(prog2, 'a_pos')
  gl.bindBuffer(gl.ARRAY_BUFFER, fsBuf)
  gl.enableVertexAttribArray(aPosLoc)
  gl.vertexAttribPointer(aPosLoc, 2, gl.FLOAT, false, 0, 0)

  // Dynamic resources (recreated on viewport change)
  let texWVal = null, texW = null, fbo1 = null
  let lastRW = 0, lastRH = 0

  function ensureTextures(rw, rh) {
    if (rw === lastRW && rh === lastRH && texWVal) return
    if (texWVal) { gl.deleteTexture(texWVal); gl.deleteTexture(texW); gl.deleteFramebuffer(fbo1) }
    texWVal = createFloatTex(gl, rw, rh)
    texW = createFloatTex(gl, rw, rh)
    fbo1 = gl.createFramebuffer()
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo1)
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texWVal, 0)
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT1, gl.TEXTURE_2D, texW, 0)
    gl.drawBuffers([gl.COLOR_ATTACHMENT0, gl.COLOR_ATTACHMENT1])
    lastRW = rw; lastRH = rh
  }

  return {
    canvas, gl, n, prog1, prog2, lutTex,
    getTexWVal: () => texWVal,
    getTexW: () => texW,
    getFbo1: () => fbo1,
    ensureTextures,
    destroy() {
      const lose = gl.getExtension('WEBGL_lose_context')
      if (lose) lose.loseContext()
    }
  }
}

// ======== splatDraw: per-frame render (uniform-only update) ========
export function splatDraw(state, options) {
  const t0 = performance.now()
  const {
    w, h, gridStep = 4,
    bounds,       // {swLng, swLat, neLng, neLat}
    sigma = 25, radius,
    algorithm = 'idw'
  } = options

  const gs = Math.max(1, gridStep)
  const renderW = Math.ceil(w / gs)
  const renderH = Math.ceil(h / gs)

  if (renderW < 1 || renderH < 1) return { canvas: state.canvas, timings: { gpu_total: 0 } }

  const scaledRadius = radius / gs
  const scaledSigma = sigma / gs
  const safeR = isFinite(scaledRadius) ? scaledRadius : Math.hypot(renderW, renderH)
  const isGaussian = algorithm === 'gaussian'

  const gl = state.gl
  state.canvas.width = renderW
  state.canvas.height = renderH
  state.ensureTextures(renderW, renderH)

  const tSetup = performance.now()

  // ---- PASS 1: accumulate ----
  gl.useProgram(state.prog1)
  gl.bindFramebuffer(gl.FRAMEBUFFER, state.getFbo1())
  gl.viewport(0, 0, renderW, renderH)
  gl.clearColor(0, 0, 0, 0)
  gl.clear(gl.COLOR_BUFFER_BIT)
  gl.enable(gl.BLEND)
  gl.blendFunc(gl.ONE, gl.ONE)

  gl.uniform4f(gl.getUniformLocation(state.prog1, 'u_bounds'),
    bounds.swLng, bounds.swLat, bounds.neLng, bounds.neLat)
  gl.uniform2f(gl.getUniformLocation(state.prog1, 'u_viewport'), w, h)
  gl.uniform1f(gl.getUniformLocation(state.prog1, 'u_gridStep'), gs)
  gl.uniform2f(gl.getUniformLocation(state.prog1, 'u_scale'), 1.0 / renderW, 1.0 / renderH)
  gl.uniform1f(gl.getUniformLocation(state.prog1, 'u_radius'), safeR)
  gl.uniform1f(gl.getUniformLocation(state.prog1, 'u_radius2'), safeR * safeR)
  gl.uniform1f(gl.getUniformLocation(state.prog1, 'u_h'), renderH)
  gl.uniform1f(gl.getUniformLocation(state.prog1, 'u_sigma'), isGaussian ? scaledSigma : 0.0)

  const tPass1_0 = performance.now()
  gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, state.n)
  const tPass1_1 = performance.now()

  // ---- PASS 2: composite to canvas ----
  gl.disable(gl.BLEND)
  gl.bindFramebuffer(gl.FRAMEBUFFER, null)
  gl.viewport(0, 0, renderW, renderH)
  gl.clearColor(0, 0, 0, 0)
  gl.clear(gl.COLOR_BUFFER_BIT)

  gl.useProgram(state.prog2)
  gl.activeTexture(gl.TEXTURE0)
  gl.bindTexture(gl.TEXTURE_2D, state.getTexWVal())
  gl.activeTexture(gl.TEXTURE1)
  gl.bindTexture(gl.TEXTURE_2D, state.getTexW())
  gl.activeTexture(gl.TEXTURE2)
  gl.bindTexture(gl.TEXTURE_2D, state.lutTex)

  const tPass2_0 = performance.now()
  gl.drawArrays(gl.TRIANGLES, 0, 6)
  const tPass2_1 = performance.now()

  gl.finish()
  const tFinish = performance.now()

  return {
    canvas: state.canvas,
    timings: {
      gpu_setup:  tPass1_0 - tSetup,
      gpu_pass1:  tPass1_1 - tPass1_0,
      gpu_pass2:  tPass2_1 - tPass2_0,
      gpu_finish: tFinish - tPass2_1,
      gpu_total:  tFinish - t0
    }
  }
}
