import { getSunPosition, getSolarElevation } from './solar.js';
import { cities } from './cities.js';

const COLORS = {
  ocean: { day: [25, 100, 170], night: [12, 20, 45] },
  cityGlow: [255, 200, 100],
  cityCore: [255, 240, 200],
};

const BIOMES = [
  { minLat: 70, day: [220, 225, 230], night: [55, 60, 70] },
  { minLat: 55, day: [40, 85, 45], night: [18, 30, 22] },
  { minLat: 40, day: [50, 115, 50], night: [20, 38, 22] },
  { minLat: 30, day: [95, 135, 55], night: [30, 42, 22] },
  { minLat: 15, day: [130, 145, 60], night: [38, 44, 24] },
  { minLat: -15, day: [30, 100, 35], night: [16, 34, 18] },
  { minLat: -30, day: [110, 140, 55], night: [35, 42, 22] },
  { minLat: -55, day: [55, 110, 50], night: [22, 36, 22] },
  { minLat: -70, day: [60, 95, 55], night: [24, 32, 24] },
  { minLat: -90, day: [215, 220, 228], night: [52, 58, 68] },
];

let worldData = null;
let landFeatures = null;
let coastlines = null;
let projection = null;
let pathGenerator = null;
let canvas, ctx;
let mapCanvas, mapCtx;
let nightCanvas, nightCtx;
let cityCanvas, cityCtx;

// Cached composite frame — used for smooth panning/zooming
let compositeCanvas, compositeCtx;

// View state
let rotateLon = 0;
let rotateLat = 0;
let zoomScale = 1;
let baseScale = 1;
const MIN_ZOOM = 0.8;
const MAX_ZOOM = 12;

// The view state at which the cached composite was rendered
let cachedRotLon = null;
let cachedRotLat = null;
let cachedZoom = null;

// Pan state
let isDragging = false;
let dragStartX = 0;
let dragStartY = 0;
let dragStartRotLon = 0;
let dragStartRotLat = 0;

// Time offset in minutes from "now"
let timeOffsetMinutes = 0;

// Debounce timer for full re-render
let fullRenderTimer = null;
const FULL_RENDER_DELAY = 150; // ms after interaction stops

// Smooth zoom interpolation
let targetZoom = 1;
let zoomAnimFrame = null;

async function init() {
  canvas = document.getElementById('map');
  ctx = canvas.getContext('2d');

  resize();
  window.addEventListener('resize', () => {
    resize();
    fullRender();
  });

  // Loading message
  const dpr = window.devicePixelRatio || 1;
  ctx.fillStyle = '#0a0e1a';
  ctx.fillRect(0, 0, canvas.width / dpr, canvas.height / dpr);
  ctx.fillStyle = '#445';
  ctx.font = '16px "Inter", sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Loading world data...', window.innerWidth / 2, window.innerHeight / 2);

  const [topoResponse, userPos] = await Promise.all([
    fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-50m.json'),
    getUserLocation(),
  ]);

  const topo = await topoResponse.json();
  worldData = topojson.feature(topo, topo.objects.countries);
  landFeatures = topojson.feature(topo, topo.objects.land);
  coastlines = topojson.mesh(topo, topo.objects.countries, (a, b) => a !== b);

  if (userPos) {
    rotateLon = -userPos.longitude;
  }

  mapCanvas = document.createElement('canvas');
  mapCtx = mapCanvas.getContext('2d');
  nightCanvas = document.createElement('canvas');
  nightCtx = nightCanvas.getContext('2d');
  cityCanvas = document.createElement('canvas');
  cityCtx = cityCanvas.getContext('2d');
  compositeCanvas = document.createElement('canvas');
  compositeCtx = compositeCanvas.getContext('2d');

  targetZoom = zoomScale;
  setupProjection();
  setupInteractions();
  setupTimeSlider();
  startLoop();
}

function getUserLocation() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve(null);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      () => resolve(null),
      { timeout: 5000 }
    );
  });
}

function resize() {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = window.innerWidth * dpr;
  canvas.height = window.innerHeight * dpr;
  canvas.style.width = window.innerWidth + 'px';
  canvas.style.height = window.innerHeight + 'px';
  ctx.scale(dpr, dpr);

  if (mapCanvas) {
    cachedRotLon = null; // invalidate cache
    setupProjection();
  }
}

function setupProjection() {
  const w = window.innerWidth;
  const h = window.innerHeight;

  [mapCanvas, nightCanvas, cityCanvas, compositeCanvas].forEach(c => {
    c.width = w;
    c.height = h;
  });

  const tempProj = d3.geoNaturalEarth1()
    .fitSize([w * 0.92, h * 0.88], { type: "Sphere" });
  baseScale = tempProj.scale();

  projection = d3.geoNaturalEarth1()
    .rotate([rotateLon, rotateLat])
    .scale(baseScale * zoomScale)
    .translate([w / 2, h / 2]);

  pathGenerator = d3.geoPath(projection);
}

function updateProjection() {
  projection
    .rotate([rotateLon, rotateLat])
    .scale(baseScale * zoomScale)
    .translate([window.innerWidth / 2, window.innerHeight / 2]);

  pathGenerator = d3.geoPath(projection);
}

// ── Smooth interaction rendering ──

/**
 * During drag/zoom, draw the cached composite with a canvas transform
 * to give instant visual feedback. Schedule a full re-render for when
 * interaction settles.
 */
function quickRedraw() {
  if (cachedRotLon === null) {
    // No cache yet, do a full render
    fullRender();
    return;
  }

  const w = window.innerWidth;
  const h = window.innerHeight;

  // Compute the visual offset between cached state and current state
  // We approximate: delta in rotation → pixel shift at current scale
  const dLon = rotateLon - cachedRotLon;
  const dLat = rotateLat - cachedRotLat;
  const pixelsPerDeg = (baseScale * cachedZoom) * Math.PI / 180;
  const dx = dLon * pixelsPerDeg;
  const dy = -dLat * pixelsPerDeg;
  const scaleRatio = zoomScale / cachedZoom;

  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const dpr = window.devicePixelRatio || 1;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.restore();

  // Draw background
  ctx.fillStyle = '#060a14';
  ctx.fillRect(0, 0, w, h);

  // Apply transform to cached image
  ctx.save();
  ctx.translate(w / 2, h / 2);
  ctx.scale(scaleRatio, scaleRatio);
  ctx.translate(-w / 2 + dx, -h / 2 + dy);
  ctx.drawImage(compositeCanvas, 0, 0);
  ctx.restore();

  // Schedule full re-render
  scheduleFullRender();
}

function scheduleFullRender() {
  clearTimeout(fullRenderTimer);
  fullRenderTimer = setTimeout(() => {
    fullRender();
  }, FULL_RENDER_DELAY);
}

function fullRender() {
  clearTimeout(fullRenderTimer);
  updateProjection();
  render();
  // Cache current state
  cachedRotLon = rotateLon;
  cachedRotLat = rotateLat;
  cachedZoom = zoomScale;
}

// ── Smooth zoom animation ──

function animateZoom() {
  const diff = targetZoom - zoomScale;
  if (Math.abs(diff) < 0.001) {
    zoomScale = targetZoom;
    zoomAnimFrame = null;
    fullRender();
    return;
  }

  // Exponential ease — covers 20% of remaining distance per frame
  zoomScale += diff * 0.2;
  quickRedraw();

  zoomAnimFrame = requestAnimationFrame(animateZoom);
}

function startZoomAnimation() {
  if (!zoomAnimFrame) {
    zoomAnimFrame = requestAnimationFrame(animateZoom);
  }
}

// ── Interactions ──

function setupInteractions() {
  // Mouse wheel zoom — smooth animated
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY > 0 ? 0.85 : 1.18;
    targetZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, targetZoom * zoomFactor));
    startZoomAnimation();
  }, { passive: false });

  // Mouse drag pan
  canvas.addEventListener('mousedown', (e) => {
    isDragging = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    dragStartRotLon = rotateLon;
    dragStartRotLat = rotateLat;
  });

  window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const sensitivity = 0.3 / zoomScale;
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;
    rotateLon = dragStartRotLon + dx * sensitivity;
    rotateLat = clamp(dragStartRotLat - dy * sensitivity, -60, 60);
    quickRedraw();
  });

  window.addEventListener('mouseup', () => {
    if (isDragging) {
      isDragging = false;
      fullRender();
    }
  });

  // Touch support
  let lastTouchDist = 0;
  let touchStartRotLon = 0;
  let touchStartRotLat = 0;
  let touchStartX = 0;
  let touchStartY = 0;

  canvas.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) {
      isDragging = true;
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
      touchStartRotLon = rotateLon;
      touchStartRotLat = rotateLat;
    } else if (e.touches.length === 2) {
      isDragging = false;
      lastTouchDist = Math.hypot(
        e.touches[1].clientX - e.touches[0].clientX,
        e.touches[1].clientY - e.touches[0].clientY
      );
    }
    e.preventDefault();
  }, { passive: false });

  canvas.addEventListener('touchmove', (e) => {
    if (e.touches.length === 1 && isDragging) {
      const sensitivity = 0.3 / zoomScale;
      const dx = e.touches[0].clientX - touchStartX;
      const dy = e.touches[0].clientY - touchStartY;
      rotateLon = touchStartRotLon + dx * sensitivity;
      rotateLat = clamp(touchStartRotLat - dy * sensitivity, -60, 60);
      quickRedraw();
    } else if (e.touches.length === 2) {
      const dist = Math.hypot(
        e.touches[1].clientX - e.touches[0].clientX,
        e.touches[1].clientY - e.touches[0].clientY
      );
      if (lastTouchDist > 0) {
        const factor = dist / lastTouchDist;
        targetZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoomScale * factor));
        zoomScale = targetZoom; // immediate for pinch
        quickRedraw();
      }
      lastTouchDist = dist;
    }
    e.preventDefault();
  }, { passive: false });

  canvas.addEventListener('touchend', () => {
    if (isDragging) {
      isDragging = false;
      fullRender();
    }
    lastTouchDist = 0;
  });

  // Double-click to reset view
  canvas.addEventListener('dblclick', (e) => {
    e.preventDefault();
    targetZoom = 1;
    rotateLat = 0;
    startZoomAnimation();
  });
}

// ── Time Slider ──

function setupTimeSlider() {
  const slider = document.getElementById('time-slider');
  const resetBtn = document.getElementById('reset-time');

  slider.addEventListener('input', () => {
    timeOffsetMinutes = parseInt(slider.value, 10);
    updateTimeLabel();
    fullRender();
  });

  resetBtn.addEventListener('click', () => {
    timeOffsetMinutes = 0;
    slider.value = 0;
    updateTimeLabel();
    fullRender();
  });
}

function updateTimeLabel() {
  const label = document.getElementById('time-label');
  if (timeOffsetMinutes === 0) {
    label.textContent = 'Now';
    label.style.color = 'rgba(200, 210, 230, 0.55)';
  } else {
    const mins = Math.abs(timeOffsetMinutes) % 60;
    const simTime = getSimulatedTime();
    const timeStr = simTime.toISOString().slice(11, 16) + ' UTC';
    const sign = timeOffsetMinutes > 0 ? '+' : '';
    label.textContent = `${sign}${Math.floor(timeOffsetMinutes / 60)}h${mins > 0 ? String(mins).padStart(2, '0') + 'm' : ''}  \u2022  ${timeStr}`;
    label.style.color = 'rgba(255, 220, 130, 0.7)';
  }
}

function getSimulatedTime() {
  return new Date(Date.now() + timeOffsetMinutes * 60000);
}

// ── Rendering ──

function startLoop() {
  fullRender();
  setInterval(fullRender, 30000);
  updateClock();
  setInterval(updateClock, 1000);
}

function updateClock() {
  const now = new Date();
  const el = document.getElementById('clock');
  if (el) {
    el.textContent = now.toLocaleTimeString('en-US', {
      hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
      timeZoneName: 'short'
    }) + '  \u2022  ' + now.toISOString().slice(0, 19).replace('T', ' ') + ' UTC';
  }
}

function render() {
  const simTime = getSimulatedTime();
  const sunPos = getSunPosition(simTime);
  const w = window.innerWidth;
  const h = window.innerHeight;

  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.restore();

  drawBaseMap(mapCtx, w, h);
  drawNightOverlay(nightCtx, w, h, sunPos);
  drawCityLights(cityCtx, w, h, sunPos);

  // Build composite on offscreen canvas
  compositeCtx.fillStyle = '#060a14';
  compositeCtx.fillRect(0, 0, w, h);

  compositeCtx.drawImage(mapCanvas, 0, 0);

  compositeCtx.globalCompositeOperation = 'multiply';
  compositeCtx.drawImage(nightCanvas, 0, 0);
  compositeCtx.globalCompositeOperation = 'source-over';

  // Atmosphere on composite
  compositeCtx.beginPath();
  pathGenerator.context(compositeCtx);
  pathGenerator({ type: "Sphere" });
  compositeCtx.strokeStyle = 'rgba(100, 180, 255, 0.12)';
  compositeCtx.lineWidth = 3;
  compositeCtx.stroke();
  compositeCtx.beginPath();
  pathGenerator({ type: "Sphere" });
  compositeCtx.strokeStyle = 'rgba(80, 150, 255, 0.06)';
  compositeCtx.lineWidth = 6;
  compositeCtx.stroke();

  compositeCtx.globalCompositeOperation = 'screen';
  compositeCtx.drawImage(cityCanvas, 0, 0);
  compositeCtx.globalCompositeOperation = 'source-over';

  // Graticule
  const gridStep = zoomScale > 3 ? 10 : zoomScale > 1.5 ? 15 : 30;
  const graticule = d3.geoGraticule().step([gridStep, gridStep])();
  compositeCtx.beginPath();
  pathGenerator.context(compositeCtx);
  pathGenerator(graticule);
  compositeCtx.strokeStyle = 'rgba(255, 255, 255, 0.045)';
  compositeCtx.lineWidth = 0.5;
  compositeCtx.stroke();

  // Sun indicator
  drawSunIndicator(compositeCtx, sunPos);

  // Blit composite to main canvas
  ctx.fillStyle = '#060a14';
  ctx.fillRect(0, 0, w, h);
  ctx.drawImage(compositeCanvas, 0, 0);

  // Vignette on main canvas (stays fixed, not cached)
  drawVignette(ctx, w, h);
}

function getBiomeColor(lat, isDay) {
  const key = isDay ? 'day' : 'night';
  for (let i = 0; i < BIOMES.length - 1; i++) {
    if (lat <= BIOMES[i].minLat && lat > BIOMES[i + 1].minLat) {
      const range = BIOMES[i].minLat - BIOMES[i + 1].minLat;
      const t = (lat - BIOMES[i + 1].minLat) / range;
      return [
        Math.round(BIOMES[i + 1][key][0] + (BIOMES[i][key][0] - BIOMES[i + 1][key][0]) * t),
        Math.round(BIOMES[i + 1][key][1] + (BIOMES[i][key][1] - BIOMES[i + 1][key][1]) * t),
        Math.round(BIOMES[i + 1][key][2] + (BIOMES[i][key][2] - BIOMES[i + 1][key][2]) * t),
      ];
    }
  }
  if (lat >= BIOMES[0].minLat) return BIOMES[0][key];
  return BIOMES[BIOMES.length - 1][key];
}

function drawBaseMap(c, w, h) {
  c.clearRect(0, 0, w, h);

  c.beginPath();
  pathGenerator.context(c);
  pathGenerator({ type: "Sphere" });
  c.fillStyle = `rgb(${COLORS.ocean.day.join(',')})`;
  c.fill();

  const cx = w / 2, cy = h / 2;
  const oceanGrad = c.createRadialGradient(cx, cy * 0.8, 0, cx, cy, Math.max(w, h) * 0.5);
  oceanGrad.addColorStop(0, 'rgba(40, 130, 200, 0.15)');
  oceanGrad.addColorStop(1, 'rgba(15, 60, 120, 0.1)');
  c.beginPath();
  pathGenerator({ type: "Sphere" });
  c.fillStyle = oceanGrad;
  c.fill();

  if (worldData) {
    worldData.features.forEach((feature) => {
      const centroid = d3.geoCentroid(feature);
      const lat = centroid[1];
      const color = getBiomeColor(lat, true);
      const hash = simpleHash(JSON.stringify(feature.id || feature.properties));
      const variation = (hash % 20) - 10;

      c.beginPath();
      pathGenerator(feature);
      c.fillStyle = `rgb(${clamp(color[0] + variation, 0, 255)}, ${clamp(color[1] + variation * 0.5, 0, 255)}, ${clamp(color[2] + variation * 0.3, 0, 255)})`;
      c.fill();
    });

    c.beginPath();
    pathGenerator(landFeatures);
    c.strokeStyle = 'rgba(180, 200, 160, 0.25)';
    c.lineWidth = 1.2;
    c.stroke();

    if (coastlines) {
      c.beginPath();
      pathGenerator(coastlines);
      c.strokeStyle = 'rgba(80, 100, 70, 0.2)';
      c.lineWidth = 0.4;
      c.stroke();
    }

    c.beginPath();
    pathGenerator(landFeatures);
    c.strokeStyle = 'rgba(0, 30, 0, 0.12)';
    c.lineWidth = 2.5;
    c.stroke();

    c.beginPath();
    pathGenerator(landFeatures);
    c.strokeStyle = 'rgba(180, 200, 160, 0.18)';
    c.lineWidth = 0.8;
    c.stroke();
  }
}

function drawNightOverlay(c, w, h, sunPos) {
  c.clearRect(0, 0, w, h);
  c.fillStyle = '#ffffff';
  c.fillRect(0, 0, w, h);

  const imageData = c.getImageData(0, 0, w, h);
  const data = imageData.data;

  const step = zoomScale > 2 ? 2 : 3;
  const values = new Float32Array(w * h);

  for (let y = 0; y < h; y += step) {
    for (let x = 0; x < w; x += step) {
      const coords = projection.invert([x, y]);
      if (!coords || isNaN(coords[0])) {
        values[y * w + x] = -999;
        continue;
      }
      values[y * w + x] = getSolarElevation(coords[1], coords[0], sunPos);
    }
  }

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (y % step === 0 && x % step === 0) continue;
      const sx = Math.round(x / step) * step;
      const sy = Math.round(y / step) * step;
      values[y * w + x] = values[Math.min(sy, h - 1) * w + Math.min(sx, w - 1)];
    }
  }

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const idx = (y * w + x) * 4;
      const elev = values[y * w + x];

      if (elev === -999) {
        data[idx] = 12;
        data[idx + 1] = 12;
        data[idx + 2] = 20;
        continue;
      }

      const twilightWidth = 0.15;
      let brightness;

      if (elev > twilightWidth) {
        brightness = 1.0;
      } else if (elev < -twilightWidth) {
        brightness = 0.30;
      } else {
        const t = (elev + twilightWidth) / (2 * twilightWidth);
        brightness = t * t * (3 - 2 * t) * 0.70 + 0.30;
      }

      let r = Math.round(255 * brightness);
      let g = Math.round(255 * brightness);
      let b = Math.round(255 * brightness);

      if (elev > -twilightWidth && elev < twilightWidth) {
        const twilightStrength = 1.0 - Math.abs(elev) / twilightWidth;
        r = Math.min(255, r + Math.round(40 * twilightStrength));
        g = Math.round(g * (1 - 0.03 * twilightStrength));
        b = Math.round(b * (1 - 0.12 * twilightStrength));
      }

      if (elev < 0) {
        const nightStrength = Math.min(1, -elev / 0.3);
        b = Math.min(255, b + Math.round(15 * nightStrength));
        r = Math.max(0, r - Math.round(5 * nightStrength));
      }

      data[idx] = r;
      data[idx + 1] = g;
      data[idx + 2] = b;
      data[idx + 3] = 255;
    }
  }

  c.putImageData(imageData, 0, 0);
}

function drawCityLights(c, w, h, sunPos) {
  c.clearRect(0, 0, w, h);
  c.fillStyle = '#000000';
  c.fillRect(0, 0, w, h);

  cities.forEach(([name, lat, lon, pop]) => {
    const pos = projection([lon, lat]);
    if (!pos) return;
    const [x, y] = pos;

    if (x < -50 || x > w + 50 || y < -50 || y > h + 50) return;

    const elev = getSolarElevation(lat, lon, sunPos);

    let intensity;
    if (elev > 0.1) {
      intensity = 0;
    } else if (elev > -0.1) {
      intensity = 1.0 - (elev + 0.1) / 0.2;
      intensity = intensity * intensity;
    } else {
      intensity = 1.0;
    }

    if (intensity <= 0) return;

    const baseSize = Math.pow(pop, 0.45) * 0.55;
    const scale = baseSize * Math.max(1, Math.sqrt(zoomScale) * 0.7);

    const outerRadius = scale * 7;
    const gradient = c.createRadialGradient(x, y, 0, x, y, outerRadius);
    const alpha = intensity * 0.4;
    gradient.addColorStop(0, `rgba(${COLORS.cityGlow.join(',')}, ${alpha})`);
    gradient.addColorStop(0.25, `rgba(${COLORS.cityGlow.join(',')}, ${alpha * 0.45})`);
    gradient.addColorStop(0.6, `rgba(255, 180, 80, ${alpha * 0.12})`);
    gradient.addColorStop(1, 'rgba(255, 200, 100, 0)');
    c.beginPath();
    c.arc(x, y, outerRadius, 0, Math.PI * 2);
    c.fillStyle = gradient;
    c.fill();

    const coreRadius = scale * 1.4;
    const coreGrad = c.createRadialGradient(x, y, 0, x, y, coreRadius);
    const coreAlpha = intensity * 0.95;
    coreGrad.addColorStop(0, `rgba(${COLORS.cityCore.join(',')}, ${coreAlpha})`);
    coreGrad.addColorStop(0.4, `rgba(${COLORS.cityGlow.join(',')}, ${coreAlpha * 0.5})`);
    coreGrad.addColorStop(1, 'rgba(255, 200, 100, 0)');
    c.beginPath();
    c.arc(x, y, coreRadius, 0, Math.PI * 2);
    c.fillStyle = coreGrad;
    c.fill();
  });
}

function drawVignette(c, w, h) {
  const gradient = c.createRadialGradient(
    w / 2, h / 2, Math.min(w, h) * 0.35,
    w / 2, h / 2, Math.max(w, h) * 0.75
  );
  gradient.addColorStop(0, 'rgba(0, 0, 0, 0)');
  gradient.addColorStop(1, 'rgba(0, 0, 0, 0.35)');
  c.fillStyle = gradient;
  c.fillRect(0, 0, w, h);
}

function drawSunIndicator(c, sunPos) {
  const pos = projection([sunPos.longitude, sunPos.latitude]);
  if (!pos) return;
  const [x, y] = pos;

  const sunGrad = c.createRadialGradient(x, y, 0, x, y, 20);
  sunGrad.addColorStop(0, 'rgba(255, 250, 200, 0.75)');
  sunGrad.addColorStop(0.3, 'rgba(255, 220, 100, 0.25)');
  sunGrad.addColorStop(1, 'rgba(255, 200, 50, 0)');
  c.beginPath();
  c.arc(x, y, 20, 0, Math.PI * 2);
  c.fillStyle = sunGrad;
  c.fill();

  c.beginPath();
  c.arc(x, y, 3.5, 0, Math.PI * 2);
  c.fillStyle = 'rgba(255, 255, 220, 0.9)';
  c.fill();
}

function simpleHash(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

// Boot
init().catch(err => {
  console.error('Failed to initialize:', err);
  const el = document.getElementById('error');
  if (el) {
    el.textContent = 'Failed to load: ' + err.message;
    el.style.display = 'block';
  }
});
