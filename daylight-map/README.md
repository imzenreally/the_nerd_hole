# Daylight Map

Real-time interactive world map showing where the sun is shining. Daylit regions glow with blue oceans and biome-colored land masses. The night side darkens with visible terrain and city lights that bloom across population centers.

![Tech](https://img.shields.io/badge/stack-vanilla%20JS%20%2B%20D3%20%2B%20Canvas-blue)
![Status](https://img.shields.io/badge/status-MVP-green)

## Features

- **Day/night terminator** — accurate solar position calculated from NOAA equations, smooth twilight gradient with warm sunset tones at the boundary
- **Biome-colored continents** — latitude-based terrain coloring (ice caps, boreal forests, temperate green, tropical, savanna, etc.) with per-country variation
- **City lights** — 170+ major cities glow on the dark side, sized by population, fading in through twilight
- **Zoom and pan** — mouse wheel zoom with smooth animation, click-drag to rotate, pinch-to-zoom on touch
- **Time slider** — scrub the sun position +/- 12 hours from now, see how daylight shifts across the globe
- **Auto-centering** — map centers on your location via the Geolocation API
- **Responsive** — full-screen canvas with HiDPI support, adapts to any viewport

## Quick Start

```bash
# Serve locally (any static file server works)
cd daylight-map
python3 -m http.server 8080

# Open http://localhost:8080
```

No build step. No dependencies to install. Just a static site that loads D3 and TopoJSON from CDN.

## How It Works

### Rendering Pipeline

The map composites five layers on offscreen canvases for performance:

```
1. BASE MAP        Ocean + landmasses with biome coloring
       ↓
2. NIGHT OVERLAY   Per-pixel solar elevation → brightness (multiply blend)
       ↓
3. ATMOSPHERE      Subtle blue glow on globe edges
       ↓
4. CITY LIGHTS     Radial gradients per city (screen blend)
       ↓
5. CHROME          Graticule grid, sun indicator, vignette
       ↓
   COMPOSITE       Cached for smooth pan/zoom transforms
```

During interaction, the cached composite is transformed with canvas `translate`/`scale` for instant feedback. A debounced full re-render fires 150ms after interaction stops.

### Solar Calculations

Sun position is computed using the NOAA solar equations:

- Julian date conversion
- Mean solar longitude and anomaly
- Equation of center (orbital eccentricity correction)
- Apparent longitude (aberration + nutation)
- Solar declination from obliquity of ecliptic
- Equation of time for sub-solar longitude
- Per-pixel solar elevation via spherical trigonometry

The terminator (day/night boundary) is rendered as a smooth gradient rather than a hard line, with a configurable twilight width of ~0.15 radians (~9 degrees).

### Night Rendering

The night overlay samples solar elevation every 2-3 pixels and interpolates between them. Brightness mapping:

| Solar Elevation | Brightness | Zone |
|----------------|-----------|------|
| > 0.15 | 100% | Full daylight |
| -0.15 to 0.15 | 30-100% (smoothstep) | Twilight |
| < -0.15 | 30% | Night |

The 30% night floor keeps continents clearly visible. A cool blue tint is applied to the night side, and warm orange tones color the twilight zone.

### City Lights

170+ cities with population data. Each city renders as a two-layer radial gradient:

- **Outer glow** — warm amber, radius scales with `population^0.45`
- **Inner core** — bright white-yellow, tight radius

Lights fade in through twilight using a quadratic ease curve and are invisible during full daylight. Glow radius scales with zoom level.

## Controls

| Input | Action |
|-------|--------|
| **Scroll wheel** | Smooth zoom (0.8x - 12x) |
| **Click + drag** | Pan / rotate the map |
| **Pinch** | Zoom on touch devices |
| **Double-click** | Reset zoom and latitude |
| **Time slider** | Scrub sun position +/- 12 hours |
| **NOW button** | Reset to current time |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Rendering | Canvas 2D API (5 offscreen layers) |
| Projection | D3.js v7 — Natural Earth projection |
| Geography | TopoJSON + Natural Earth 50m dataset |
| Solar math | Custom NOAA implementation |
| Fonts | Inter (UI) + JetBrains Mono (data) |
| Build | None — vanilla ES modules |

## Project Structure

```
daylight-map/
├── index.html          # Entry point, loads D3/TopoJSON from CDN
├── css/
│   └── style.css       # Dark theme, slider styling, overlays
└── js/
    ├── app.js          # Rendering engine, interactions, compositing
    ├── solar.js        # NOAA solar position calculations
    └── cities.js       # 170+ cities with lat/lon/population
```

## City Coverage

173 metropolitan areas across all inhabited continents:

| Region | Cities | Examples |
|--------|--------|---------|
| Asia | 42 | Tokyo, Delhi, Shanghai, Bangkok, Singapore |
| Europe | 25 | London, Paris, Moscow, Berlin, Rome |
| North America | 30 | New York, LA, Toronto, Mexico City |
| South America | 16 | Sao Paulo, Buenos Aires, Lima, Bogota |
| Africa | 13 | Lagos, Cairo, Kinshasa, Johannesburg |
| Middle East | 8 | Dubai, Istanbul, Riyadh, Tel Aviv |
| Oceania | 6 | Sydney, Melbourne, Auckland, Perth |

## Roadmap

- [ ] Realistic globe rendering (WebGL, atmospheric scattering)
- [ ] Dynamic cloud cover from satellite data
- [ ] Moon phase and position
- [ ] Sunrise/sunset times on hover
- [ ] Additional city data (smaller cities, brightness by GDP)
- [ ] Seasonal color variation (autumn foliage, snow cover)
- [ ] Dark/light theme toggle
- [ ] Shareable time-shifted URLs

## License

MIT
