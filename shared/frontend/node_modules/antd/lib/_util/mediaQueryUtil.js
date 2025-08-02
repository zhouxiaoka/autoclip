"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.removeMediaQueryListener = exports.addMediaQueryListener = void 0;
const addMediaQueryListener = (mql, handler) => {
  // Don't delete here, please keep the code compatible
  if (typeof (mql === null || mql === void 0 ? void 0 : mql.addEventListener) !== 'undefined') {
    mql.addEventListener('change', handler);
  } else if (typeof (mql === null || mql === void 0 ? void 0 : mql.addListener) !== 'undefined') {
    mql.addListener(handler);
  }
};
exports.addMediaQueryListener = addMediaQueryListener;
const removeMediaQueryListener = (mql, handler) => {
  // Don't delete here, please keep the code compatible
  if (typeof (mql === null || mql === void 0 ? void 0 : mql.removeEventListener) !== 'undefined') {
    mql.removeEventListener('change', handler);
  } else if (typeof (mql === null || mql === void 0 ? void 0 : mql.removeListener) !== 'undefined') {
    mql.removeListener(handler);
  }
};
exports.removeMediaQueryListener = removeMediaQueryListener;