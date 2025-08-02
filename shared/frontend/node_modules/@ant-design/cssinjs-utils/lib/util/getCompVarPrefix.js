"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var getCompVarPrefix = function getCompVarPrefix(component, prefix) {
  return "".concat([prefix, component.replace(/([A-Z]+)([A-Z][a-z]+)/g, '$1-$2').replace(/([a-z])([A-Z])/g, '$1-$2')].filter(Boolean).join('-'));
};
var _default = exports.default = getCompVarPrefix;