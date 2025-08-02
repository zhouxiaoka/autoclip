"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useGutter;
var _responsiveObserver = require("../../_util/responsiveObserver");
function useGutter(gutter, screens) {
  const results = [undefined, undefined];
  const normalizedGutter = Array.isArray(gutter) ? gutter : [gutter, undefined];
  // By default use as `xs`
  const mergedScreens = screens || {
    xs: true,
    sm: true,
    md: true,
    lg: true,
    xl: true,
    xxl: true
  };
  normalizedGutter.forEach((g, index) => {
    if (typeof g === 'object' && g !== null) {
      for (let i = 0; i < _responsiveObserver.responsiveArray.length; i++) {
        const breakpoint = _responsiveObserver.responsiveArray[i];
        if (mergedScreens[breakpoint] && g[breakpoint] !== undefined) {
          results[index] = g[breakpoint];
          break;
        }
      }
    } else {
      results[index] = g;
    }
  });
  return results;
}