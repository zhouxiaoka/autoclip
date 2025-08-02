"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
const isPrimitive = value => typeof value !== 'object' && typeof value !== 'function' || value === null;
var _default = exports.default = isPrimitive;