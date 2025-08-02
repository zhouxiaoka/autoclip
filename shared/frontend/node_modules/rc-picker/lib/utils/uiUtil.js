"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.getRealPlacement = getRealPlacement;
// ====================== Mode ======================
function getRealPlacement(placement, rtl) {
  if (placement !== undefined) {
    return placement;
  }
  return rtl ? 'bottomRight' : 'bottomLeft';
}