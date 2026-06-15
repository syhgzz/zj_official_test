// webgl-splat.js — GPU-accelerated IDW / Gaussian interpolation via splatting
//
// Creates an internal OffscreenCanvas with WebGL2, renders directly to its
// default framebuffer (no readPixels), and returns the canvas + timings.
//
// Returns {ok: true, canvas: OffscreenCanvas, timings: {...}} on success,
// or {ok: false} if WebGL2/float-texture is unavailable.

export function splatRender(data, options) {
  const t0 = performance.now()
  const { w, h, radius, idwPower = 2, idwEpsilon = 0.1, sigma = 25, algorithm = 'idw', opacity = 0.7, colorLut, valueMin, valueMax, gridStep = 4 } = options

  if (!data || !data.length) return { ok: false }

  const gs = Math.max(1, gridStep)
  const renderW = Math.ceil(w / gs)
  const renderH = Math.ceil(h / gs)

  const scaledRadius = radius / gs
  const scaledSigma = sigma / gs
  const safeR = isFinite(scaledRadius) ? scaledRadius : Math.hypot(renderW, renderH)
  const isGaussian = algorithm === 'gaussian'

  // --- Create internal WebGL canvas (NOT reusing caller's 2d canvas) ---
  const canvas = new OffscreenCanvas(renderW, renderH)
  const gl = canvas.getContext('webgl2', {
    antialias: false, depth: false, stencil: false,
    preserveDrawingBuffer: true, premultipliedAlpha: false
  })
  if (!gl) return { ok: false }

  const extFloat = gl.getExtension('EXT_color_buffer_float')
  if (!extFloat) return { ok: false }

  // --- Compile shaders ---
  const tSetup0 = performance.now()
  function makeShader(type, src) {
    const s = gl.createShader(type)
    gl.shaderSource(s, src)
    gl.compileShader(s)
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      console.warn('WebGL shader error:', gl.getShaderInfoLog(s))
      return null
    }
    return s
  }

  // Pass 1: Splat accumulation
  const splatVS = `#version 300 es
    in vec2 a_corner;
    in vec2 a_center;
    in float a_value;
    uniform vec2 u_scale;
    uniform float u_radius;
    out vec2 v_center;
    out float v_value;
    void main() {
      vec2 offset = (a_corner - 0.5) * u_radius * 2.0;
      vec2 pos = (a_center + offset) * u_scale * 2.0 - 1.0;
      gl_Position = vec4(pos.x, -pos.y, 0.0, 1.0);
      v_center = a_center;
      v_value = a_value;
    }`

  const splatFS = `#version 300 es
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

  const vs1 = makeShader(gl.VERTEX_SHADER, splatVS)
  const fs1 = makeShader(gl.FRAGMENT_SHADER, splatFS)
  if (!vs1 || !fs1) return { ok: false }
  const prog1 = gl.createProgram()
  gl.attachShader(prog1, vs1); gl.attachShader(prog1, fs1)
  gl.linkProgram(prog1)
  if (!gl.getProgramParameter(prog1, gl.LINK_STATUS)) return { ok: false }

  // Pass 2: Composite (no Y-flip — default framebuffer + convertToBlob handles orientation)
  const compVS = `#version 300 es
    in vec2 a_pos;
    out vec2 v_uv;
    void main() {
      gl_Position = vec4(a_pos, 0.0, 1.0);
      v_uv = a_pos * 0.5 + 0.5;
    }`

  const compFS = `#version 300 es
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

  const vs2 = makeShader(gl.VERTEX_SHADER, compVS)
  const fs2 = makeShader(gl.FRAGMENT_SHADER, compFS)
  if (!vs2 || !fs2) return { ok: false }
  const prog2 = gl.createProgram()
  gl.attachShader(prog2, vs2); gl.attachShader(prog2, fs2)
  gl.linkProgram(prog2)
  if (!gl.getProgramParameter(prog2, gl.LINK_STATUS)) return { ok: false }

  // --- Float textures ---
  function createFloatTex(iw, ih) {
    const t = gl.createTexture()
    gl.bindTexture(gl.TEXTURE_2D, t)
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, iw, ih, 0, gl.RGBA, gl.FLOAT, null)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
    return t
  }

  const texWVal = createFloatTex(renderW, renderH)
  const texW = createFloatTex(renderW, renderH)
  const fbo1 = gl.createFramebuffer()
  gl.bindFramebuffer(gl.FRAMEBUFFER, fbo1)
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texWVal, 0)
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT1, gl.TEXTURE_2D, texW, 0)
  gl.drawBuffers([gl.COLOR_ATTACHMENT0, gl.COLOR_ATTACHMENT1])
  if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) return { ok: false }

  // --- LUT texture ---
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

  // --- Static geometry ---
  const quadVerts = new Float32Array([0,0, 1,0, 1,1, 0,0, 1,1, 0,1])
  const quadBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf)
  gl.bufferData(gl.ARRAY_BUFFER, quadVerts, gl.STATIC_DRAW)

  const fsQuad = new Float32Array([-1,-1, 1,-1, 1,1, -1,-1, 1,1, -1,1])
  const fsBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, fsBuf)
  gl.bufferData(gl.ARRAY_BUFFER, fsQuad, gl.STATIC_DRAW)

  // --- Instance data (scaled to render resolution) ---
  const n = data.length
  const centers = new Float32Array(n * 2)
  const values = new Float32Array(n)
  for (let i = 0; i < n; i++) {
    centers[i * 2] = data[i].x / gs
    centers[i * 2 + 1] = data[i].y / gs
    values[i] = data[i].value
  }

  const tUpload0 = performance.now()
  const centerBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, centerBuf)
  gl.bufferData(gl.ARRAY_BUFFER, centers, gl.STATIC_DRAW)

  const valueBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, valueBuf)
  gl.bufferData(gl.ARRAY_BUFFER, values, gl.STATIC_DRAW)
  const tUpload1 = performance.now()

  // ========== PASS 1: Accumulate ==========
  gl.useProgram(prog1)
  gl.bindFramebuffer(gl.FRAMEBUFFER, fbo1)
  gl.viewport(0, 0, renderW, renderH)
  gl.clearColor(0, 0, 0, 0)
  gl.clear(gl.COLOR_BUFFER_BIT)
  gl.enable(gl.BLEND)
  gl.blendFunc(gl.ONE, gl.ONE)

  gl.uniform2f(gl.getUniformLocation(prog1, 'u_scale'), 1.0 / renderW, 1.0 / renderH)
  gl.uniform1f(gl.getUniformLocation(prog1, 'u_radius2'), safeR * safeR)
  gl.uniform1f(gl.getUniformLocation(prog1, 'u_radius'), safeR)
  gl.uniform1f(gl.getUniformLocation(prog1, 'u_power'), idwPower)
  gl.uniform1f(gl.getUniformLocation(prog1, 'u_eps'), idwEpsilon)
  gl.uniform1f(gl.getUniformLocation(prog1, 'u_h'), renderH)
  gl.uniform1f(gl.getUniformLocation(prog1, 'u_sigma'), isGaussian ? scaledSigma : 0.0)

  const aCorner = gl.getAttribLocation(prog1, 'a_corner')
  gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf)
  gl.enableVertexAttribArray(aCorner)
  gl.vertexAttribPointer(aCorner, 2, gl.FLOAT, false, 0, 0)

  const aCenter = gl.getAttribLocation(prog1, 'a_center')
  gl.bindBuffer(gl.ARRAY_BUFFER, centerBuf)
  gl.enableVertexAttribArray(aCenter)
  gl.vertexAttribPointer(aCenter, 2, gl.FLOAT, false, 0, 0)
  gl.vertexAttribDivisor(aCenter, 1)

  const aValue = gl.getAttribLocation(prog1, 'a_value')
  gl.bindBuffer(gl.ARRAY_BUFFER, valueBuf)
  gl.enableVertexAttribArray(aValue)
  gl.vertexAttribPointer(aValue, 1, gl.FLOAT, false, 0, 0)
  gl.vertexAttribDivisor(aValue, 1)

  const tPass1_0 = performance.now()
  gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, n)
  const tPass1_1 = performance.now()

  // ========== PASS 2: Composite to default framebuffer ==========
  gl.disable(gl.BLEND)
  gl.bindFramebuffer(gl.FRAMEBUFFER, null)
  gl.viewport(0, 0, renderW, renderH)
  gl.clearColor(0, 0, 0, 0)
  gl.clear(gl.COLOR_BUFFER_BIT)

  gl.useProgram(prog2)
  gl.activeTexture(gl.TEXTURE0)
  gl.bindTexture(gl.TEXTURE_2D, texWVal)
  gl.uniform1i(gl.getUniformLocation(prog2, 'u_texWVal'), 0)
  gl.activeTexture(gl.TEXTURE1)
  gl.bindTexture(gl.TEXTURE_2D, texW)
  gl.uniform1i(gl.getUniformLocation(prog2, 'u_texW'), 1)
  gl.activeTexture(gl.TEXTURE2)
  gl.bindTexture(gl.TEXTURE_2D, lutTex)
  gl.uniform1i(gl.getUniformLocation(prog2, 'u_lut'), 2)
  gl.uniform1f(gl.getUniformLocation(prog2, 'u_vMin'), valueMin)
  gl.uniform1f(gl.getUniformLocation(prog2, 'u_vRange'), valueMax - valueMin || 1.0)
  gl.uniform1f(gl.getUniformLocation(prog2, 'u_opacity'), opacity)

  const aPos = gl.getAttribLocation(prog2, 'a_pos')
  gl.bindBuffer(gl.ARRAY_BUFFER, fsBuf)
  gl.enableVertexAttribArray(aPos)
  gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0)

  const tPass2_0 = performance.now()
  gl.drawArrays(gl.TRIANGLES, 0, 6)
  const tPass2_1 = performance.now()

  gl.finish()
  const tFinish = performance.now()

  gl.deleteFramebuffer(fbo1)
  gl.deleteTexture(texWVal)
  gl.deleteTexture(texW)
  gl.deleteTexture(lutTex)

  return {
    ok: true,
    canvas,
    timings: {
      gpu_setup:   tUpload0 - tSetup0,
      gpu_upload:  tUpload1 - tUpload0,
      gpu_pass1:   tPass1_1 - tPass1_0,
      gpu_pass2:   tPass2_1 - tPass2_0,
      gpu_finish:  tFinish - tPass2_1,
      gpu_total:   tFinish - t0
    }
  }
}
