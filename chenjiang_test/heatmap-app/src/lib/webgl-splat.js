// webgl-splat.js — GPU-accelerated IDW / Gaussian interpolation via splatting

export function splatRender(data, options) {
  const { w, h, radius, idwPower = 2, idwEpsilon = 0.1, sigma = 25, algorithm = 'idw', opacity = 0.7, colorLut, valueMin, valueMax, gridStep = 4 } = options
  const safeR = isFinite(radius) ? radius : Math.hypot(w, h)
  const isGaussian = algorithm === 'gaussian'

  // Create offscreen canvas with WebGL2
  const offscreen = new OffscreenCanvas(w, h)
  const gl = offscreen.getContext('webgl2', {
    antialias: false, depth: false, stencil: false,
    preserveDrawingBuffer: false, premultipliedAlpha: false
  })
  if (!gl) return null

  const extFloat = gl.getExtension('EXT_color_buffer_float')
  if (!extFloat) return null // CPU fallback

  // --- Compile shaders ---
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

  // --- Pass 1: Splat accumulation ---
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
  if (!vs1 || !fs1) return null

  const prog1 = gl.createProgram()
  gl.attachShader(prog1, vs1); gl.attachShader(prog1, fs1)
  gl.linkProgram(prog1)
  if (!gl.getProgramParameter(prog1, gl.LINK_STATUS)) return null

  // --- Pass 2: Composite ---
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
  if (!vs2 || !fs2) return null

  const prog2 = gl.createProgram()
  gl.attachShader(prog2, vs2); gl.attachShader(prog2, fs2)
  gl.linkProgram(prog2)
  if (!gl.getProgramParameter(prog2, gl.LINK_STATUS)) return null

  // --- Create float textures for accumulation ---
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

  const texWVal = createFloatTex(w, h)
  const texW = createFloatTex(w, h)

  const fbo1 = gl.createFramebuffer()
  gl.bindFramebuffer(gl.FRAMEBUFFER, fbo1)
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texWVal, 0)
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT1, gl.TEXTURE_2D, texW, 0)
  gl.drawBuffers([gl.COLOR_ATTACHMENT0, gl.COLOR_ATTACHMENT1])
  if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) return null

  // --- LUT texture (RGBA8, 256x1) ---
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

  // --- Output FBO (RGBA8) ---
  const texOut = gl.createTexture()
  gl.bindTexture(gl.TEXTURE_2D, texOut)
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST)

  const fbo2 = gl.createFramebuffer()
  gl.bindFramebuffer(gl.FRAMEBUFFER, fbo2)
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texOut, 0)
  if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) return null

  // --- Quad geometry (static, in unit square) ---
  const quadVerts = new Float32Array([0,0, 1,0, 1,1, 0,0, 1,1, 0,1]) // 6 vertices
  const quadBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf)
  gl.bufferData(gl.ARRAY_BUFFER, quadVerts, gl.STATIC_DRAW)

  // --- Fullscreen quad for composite ---
  const fsQuad = new Float32Array([-1,-1, 1,-1, 1,1, -1,-1, 1,1, -1,1])
  const fsBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, fsBuf)
  gl.bufferData(gl.ARRAY_BUFFER, fsQuad, gl.STATIC_DRAW)

  // --- Instance data: centers and values ---
  const n = data.length
  const centers = new Float32Array(n * 2)
  const values = new Float32Array(n)
  for (let i = 0; i < n; i++) {
    centers[i * 2] = data[i].x
    centers[i * 2 + 1] = data[i].y
    values[i] = data[i].value
  }

  const centerBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, centerBuf)
  gl.bufferData(gl.ARRAY_BUFFER, centers, gl.STATIC_DRAW)

  const valueBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, valueBuf)
  gl.bufferData(gl.ARRAY_BUFFER, values, gl.STATIC_DRAW)

  // ========== PASS 1: Accumulate ==========
  gl.useProgram(prog1)
  gl.bindFramebuffer(gl.FRAMEBUFFER, fbo1)
  gl.viewport(0, 0, w, h)
  gl.clearColor(0, 0, 0, 0)
  gl.clear(gl.COLOR_BUFFER_BIT)
  gl.enable(gl.BLEND)
  gl.blendFunc(gl.ONE, gl.ONE)

  gl.uniform2f(gl.getUniformLocation(prog1, 'u_scale'), 1.0 / w, 1.0 / h)
  gl.uniform1f(gl.getUniformLocation(prog1, 'u_radius2'), safeR * safeR)
  gl.uniform1f(gl.getUniformLocation(prog1, 'u_radius'), safeR)
  gl.uniform1f(gl.getUniformLocation(prog1, 'u_power'), idwPower)
  gl.uniform1f(gl.getUniformLocation(prog1, 'u_eps'), idwEpsilon)
  gl.uniform1f(gl.getUniformLocation(prog1, 'u_h'), h)
  gl.uniform1f(gl.getUniformLocation(prog1, 'u_sigma'), isGaussian ? sigma : 0.0)

  // Quad corner (per-vertex, divisor 0)
  const aCorner = gl.getAttribLocation(prog1, 'a_corner')
  gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf)
  gl.enableVertexAttribArray(aCorner)
  gl.vertexAttribPointer(aCorner, 2, gl.FLOAT, false, 0, 0)

  // Center (per-instance, divisor 1)
  const aCenter = gl.getAttribLocation(prog1, 'a_center')
  gl.bindBuffer(gl.ARRAY_BUFFER, centerBuf)
  gl.enableVertexAttribArray(aCenter)
  gl.vertexAttribPointer(aCenter, 2, gl.FLOAT, false, 0, 0)
  gl.vertexAttribDivisor(aCenter, 1)

  // Value (per-instance, divisor 1)
  const aValue = gl.getAttribLocation(prog1, 'a_value')
  gl.bindBuffer(gl.ARRAY_BUFFER, valueBuf)
  gl.enableVertexAttribArray(aValue)
  gl.vertexAttribPointer(aValue, 1, gl.FLOAT, false, 0, 0)
  gl.vertexAttribDivisor(aValue, 1)

  gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, n)

  // ========== PASS 2: Composite ==========
  gl.disable(gl.BLEND)
  gl.bindFramebuffer(gl.FRAMEBUFFER, fbo2)
  gl.viewport(0, 0, w, h)
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
  gl.drawArrays(gl.TRIANGLES, 0, 6)

  // ========== Read back ==========
  const pixels = new Uint8Array(w * h * 4)
  gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, pixels)

  // Flip Y: WebGL row 0=bottom, Canvas row 0=top
  const rowSize = w * 4
  const tmpRow = new Uint8Array(rowSize)
  for (let r = 0; r < h >> 1; r++) {
    const top = r * rowSize, bot = (h - 1 - r) * rowSize
    tmpRow.set(pixels.subarray(top, top + rowSize))
    pixels.copyWithin(top, bot, bot + rowSize)
    pixels.set(tmpRow, bot)
  }

  // Cleanup
  gl.deleteFramebuffer(fbo1); gl.deleteFramebuffer(fbo2)
  gl.deleteTexture(texWVal); gl.deleteTexture(texW); gl.deleteTexture(texOut); gl.deleteTexture(lutTex)

  // Block-fill to match CPU gridStep behavior
  if (gridStep > 1) {
    const gs = gridStep
    for (let y = 0; y < h; y += gs) {
      for (let x = 0; x < w; x += gs) {
        const si = (y * w + x) * 4
        const r = pixels[si], g = pixels[si + 1], b = pixels[si + 2], a = pixels[si + 3]
        const my = Math.min(y + gs, h), mx = Math.min(x + gs, w)
        for (let dy = y; dy < my; dy++) {
          for (let dx = x; dx < mx; dx++) {
            const di = (dy * w + dx) * 4
            pixels[di] = r; pixels[di + 1] = g; pixels[di + 2] = b; pixels[di + 3] = a
          }
        }
      }
    }
  }

  return pixels
}
