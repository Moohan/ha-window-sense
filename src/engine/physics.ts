/**
 * Building physics and psychrometric equations
 * Implements Magnus-Tetens formula for absolute humidity and dew point.
 */

/**
 * Calculates saturation vapor pressure in hPa for temperature in °C
 */
export function saturationVaporPressure(tempC: number): number {
  return 6.112 * Math.exp((17.67 * tempC) / (tempC + 243.5));
}

/**
 * Calculates actual vapor pressure in hPa
 */
export function actualVaporPressure(tempC: number, rhPercent: number): number {
  const sat = saturationVaporPressure(tempC);
  return (Math.max(0, Math.min(100, rhPercent)) / 100) * sat;
}

/**
 * Calculates Absolute Humidity in g/m³
 * Absolute humidity is conserved unless outdoor air is exchanged or moisture is added/removed.
 */
export function calculateAbsoluteHumidity(tempC: number, rhPercent: number): number {
  const vp = actualVaporPressure(tempC, rhPercent);
  const tempK = tempC + 273.15;
  return (216.7 * vp) / tempK;
}

/**
 * Calculates Dew Point in °C
 */
export function calculateDewPoint(tempC: number, rhPercent: number): number {
  const vp = actualVaporPressure(tempC, rhPercent);
  if (vp <= 0) return -50;
  const lnVp = Math.log(vp / 6.112);
  const denom = 17.67 - lnVp;
  if (denom === 0) return tempC;
  return (243.5 * lnVp) / denom;
}
