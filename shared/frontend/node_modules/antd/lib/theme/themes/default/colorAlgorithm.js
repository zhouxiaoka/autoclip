"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.getSolidColor = exports.getAlphaColor = void 0;
var _fastColor = require("@ant-design/fast-color");
const getAlphaColor = (baseColor, alpha) => new _fastColor.FastColor(baseColor).setA(alpha).toRgbString();
exports.getAlphaColor = getAlphaColor;
const getSolidColor = (baseColor, brightness) => {
  const instance = new _fastColor.FastColor(baseColor);
  return instance.darken(brightness).toHexString();
};
exports.getSolidColor = getSolidColor;