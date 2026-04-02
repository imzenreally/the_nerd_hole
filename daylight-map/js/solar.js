/**
 * Solar position calculations for day/night terminator.
 * Based on NOAA solar equations.
 */

export function getSunPosition(date) {
  const jd = toJulianDate(date);
  const T = (jd - 2451545.0) / 36525.0;

  // Solar coordinates
  const L0 = mod(280.46646 + T * (36000.76983 + 0.0003032 * T), 360);
  const M = mod(357.52911 + T * (35999.05029 - 0.0001537 * T), 360);
  const Mrad = M * Math.PI / 180;

  const C = (1.914602 - T * (0.004817 + 0.000014 * T)) * Math.sin(Mrad)
    + (0.019993 - 0.000101 * T) * Math.sin(2 * Mrad)
    + 0.000289 * Math.sin(3 * Mrad);

  const sunLon = L0 + C;
  const omega = 125.04 - 1934.136 * T;
  const apparentLon = sunLon - 0.00569 - 0.00478 * Math.sin(omega * Math.PI / 180);

  // Obliquity of ecliptic
  const obliquity = 23.439291 - 0.0130042 * T;
  const oblRad = obliquity * Math.PI / 180;
  const appLonRad = apparentLon * Math.PI / 180;

  // Declination
  const sinDec = Math.sin(oblRad) * Math.sin(appLonRad);
  const declination = Math.asin(sinDec) * 180 / Math.PI;

  // Equation of time (minutes)
  const y = Math.tan(oblRad / 2) ** 2;
  const L0rad = L0 * Math.PI / 180;
  const e = 0.016708634 - T * (0.000042037 + 0.0000001267 * T);
  const eqTime = 4 * (180 / Math.PI) * (
    y * Math.sin(2 * L0rad)
    - 2 * e * Math.sin(Mrad)
    + 4 * e * y * Math.sin(Mrad) * Math.cos(2 * L0rad)
    - 0.5 * y * y * Math.sin(4 * L0rad)
    - 1.25 * e * e * Math.sin(2 * Mrad)
  );

  // Sub-solar point
  const utcHours = date.getUTCHours() + date.getUTCMinutes() / 60 + date.getUTCSeconds() / 3600;
  const solarNoonOffset = eqTime / 60;
  const longitude = -((utcHours - 12 + solarNoonOffset) * 15);

  return {
    latitude: declination,
    longitude: mod(longitude + 180, 360) - 180
  };
}

/**
 * Returns the solar elevation angle for a given point and sun position.
 * Result is in range [-1, 1] where positive = day, negative = night.
 */
export function getSolarElevation(lat, lon, sunPos) {
  const latRad = lat * Math.PI / 180;
  const sunLatRad = sunPos.latitude * Math.PI / 180;
  const dLon = (lon - sunPos.longitude) * Math.PI / 180;

  return Math.sin(latRad) * Math.sin(sunLatRad)
    + Math.cos(latRad) * Math.cos(sunLatRad) * Math.cos(dLon);
}

/**
 * Generate terminator path as array of [lon, lat] points.
 */
export function getTerminatorPath(sunPos, steps = 360) {
  const points = [];
  const sunLatRad = sunPos.latitude * Math.PI / 180;

  for (let i = 0; i <= steps; i++) {
    const lon = -180 + (360 * i / steps);
    const dLon = (lon - sunPos.longitude) * Math.PI / 180;

    // Latitude where solar elevation = 0
    const lat = Math.atan(-Math.cos(dLon) / Math.tan(sunLatRad)) * 180 / Math.PI;
    points.push([lon, lat]);
  }

  return points;
}

/**
 * Build a GeoJSON polygon for the night side of the earth.
 */
export function getNightGeoJSON(sunPos, steps = 360) {
  const terminator = getTerminatorPath(sunPos, steps);

  // Determine which pole is in darkness
  const nightPoleLatitude = sunPos.latitude > 0 ? -90 : 90;

  const nightPoly = [];

  // Start from one edge, trace terminator, close around the dark pole
  for (const pt of terminator) {
    nightPoly.push(pt);
  }

  // Close around the dark pole
  nightPoly.push([180, terminator[terminator.length - 1][1]]);
  nightPoly.push([180, nightPoleLatitude]);
  nightPoly.push([-180, nightPoleLatitude]);
  nightPoly.push([-180, terminator[0][1]]);
  nightPoly.push(terminator[0]);

  return {
    type: "Feature",
    geometry: {
      type: "Polygon",
      coordinates: [nightPoly]
    }
  };
}

function toJulianDate(date) {
  return date.getTime() / 86400000 + 2440587.5;
}

function mod(a, b) {
  return ((a % b) + b) % b;
}
