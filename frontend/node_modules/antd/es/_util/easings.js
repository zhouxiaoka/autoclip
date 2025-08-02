export function easeInOutCubic(t, b, c, d) {
  const cc = c - b;
  // biome-ignore lint: it is a common easing function
  t /= d / 2;
  if (t < 1) {
    return cc / 2 * t * t * t + b;
  }
  // biome-ignore lint: it is a common easing function
  return cc / 2 * ((t -= 2) * t * t + 2) + b;
}