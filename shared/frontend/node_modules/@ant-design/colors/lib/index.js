"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
var _exportNames = {
  generate: true
};
Object.defineProperty(exports, "generate", {
  enumerable: true,
  get: function get() {
    return _generate.default;
  }
});
var _generate = _interopRequireDefault(require("./generate"));
var _presets = require("./presets");
Object.keys(_presets).forEach(function (key) {
  if (key === "default" || key === "__esModule") return;
  if (Object.prototype.hasOwnProperty.call(_exportNames, key)) return;
  if (key in exports && exports[key] === _presets[key]) return;
  Object.defineProperty(exports, key, {
    enumerable: true,
    get: function get() {
      return _presets[key];
    }
  });
});
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }