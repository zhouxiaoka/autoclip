"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
var _FastColor = require("./FastColor");
Object.keys(_FastColor).forEach(function (key) {
  if (key === "default" || key === "__esModule") return;
  if (key in exports && exports[key] === _FastColor[key]) return;
  Object.defineProperty(exports, key, {
    enumerable: true,
    get: function () {
      return _FastColor[key];
    }
  });
});
var _types = require("./types");
Object.keys(_types).forEach(function (key) {
  if (key === "default" || key === "__esModule") return;
  if (key in exports && exports[key] === _types[key]) return;
  Object.defineProperty(exports, key, {
    enumerable: true,
    get: function () {
      return _types[key];
    }
  });
});