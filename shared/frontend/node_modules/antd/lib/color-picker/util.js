"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.getRoundNumber = exports.getGradientPercentColor = exports.getColorAlpha = exports.generateColor = exports.genAlphaColor = void 0;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var _colorPicker = require("@rc-component/color-picker");
var _color = require("./color");
const generateColor = color => {
  if (color instanceof _color.AggregationColor) {
    return color;
  }
  return new _color.AggregationColor(color);
};
exports.generateColor = generateColor;
const getRoundNumber = value => Math.round(Number(value || 0));
exports.getRoundNumber = getRoundNumber;
const getColorAlpha = color => getRoundNumber(color.toHsb().a * 100);
/** Return the color whose `alpha` is 1 */
exports.getColorAlpha = getColorAlpha;
const genAlphaColor = (color, alpha) => {
  const rgba = color.toRgb();
  // Color from hsb input may get `rgb` is (0/0/0) when `hsb.b` is 0
  // So if rgb is empty, we should get from hsb
  if (!rgba.r && !rgba.g && !rgba.b) {
    const hsba = color.toHsb();
    hsba.a = alpha || 1;
    return generateColor(hsba);
  }
  rgba.a = alpha || 1;
  return generateColor(rgba);
};
/**
 * Get percent position color. e.g. [10%-#fff, 20%-#000], 15% => #888
 */
exports.genAlphaColor = genAlphaColor;
const getGradientPercentColor = (colors, percent) => {
  const filledColors = [{
    percent: 0,
    color: colors[0].color
  }].concat((0, _toConsumableArray2.default)(colors), [{
    percent: 100,
    color: colors[colors.length - 1].color
  }]);
  for (let i = 0; i < filledColors.length - 1; i += 1) {
    const startPtg = filledColors[i].percent;
    const endPtg = filledColors[i + 1].percent;
    const startColor = filledColors[i].color;
    const endColor = filledColors[i + 1].color;
    if (startPtg <= percent && percent <= endPtg) {
      const dist = endPtg - startPtg;
      if (dist === 0) {
        return startColor;
      }
      const ratio = (percent - startPtg) / dist * 100;
      const startRcColor = new _colorPicker.Color(startColor);
      const endRcColor = new _colorPicker.Color(endColor);
      return startRcColor.mix(endRcColor, ratio).toRgbString();
    }
  }
  // This will never reach
  /* istanbul ignore next */
  return '';
};
exports.getGradientPercentColor = getGradientPercentColor;