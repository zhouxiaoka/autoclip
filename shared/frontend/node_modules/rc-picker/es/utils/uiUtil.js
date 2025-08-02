// ====================== Mode ======================
export function getRealPlacement(placement, rtl) {
  if (placement !== undefined) {
    return placement;
  }
  return rtl ? 'bottomRight' : 'bottomLeft';
}