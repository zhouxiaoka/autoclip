"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
const toList = (candidate, skipEmpty = false) => {
  if (skipEmpty && (candidate === undefined || candidate === null)) {
    return [];
  }
  return Array.isArray(candidate) ? candidate : [candidate];
};
var _default = exports.default = toList;