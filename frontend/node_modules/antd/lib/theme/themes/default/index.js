"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = derivative;
var _colors = require("@ant-design/colors");
var _seed = require("../seed");
var _genColorMapToken = _interopRequireDefault(require("../shared/genColorMapToken"));
var _genCommonMapToken = _interopRequireDefault(require("../shared/genCommonMapToken"));
var _genControlHeight = _interopRequireDefault(require("../shared/genControlHeight"));
var _genFontMapToken = _interopRequireDefault(require("../shared/genFontMapToken"));
var _genSizeMapToken = _interopRequireDefault(require("../shared/genSizeMapToken"));
var _colors2 = require("./colors");
function derivative(token) {
  // pink is deprecated name of magenta, keep this for backwards compatibility
  _colors.presetPrimaryColors.pink = _colors.presetPrimaryColors.magenta;
  _colors.presetPalettes.pink = _colors.presetPalettes.magenta;
  const colorPalettes = Object.keys(_seed.defaultPresetColors).map(colorKey => {
    const colors = token[colorKey] === _colors.presetPrimaryColors[colorKey] ? _colors.presetPalettes[colorKey] : (0, _colors.generate)(token[colorKey]);
    return Array.from({
      length: 10
    }, () => 1).reduce((prev, _, i) => {
      prev[`${colorKey}-${i + 1}`] = colors[i];
      prev[`${colorKey}${i + 1}`] = colors[i];
      return prev;
    }, {});
  }).reduce((prev, cur) => {
    // biome-ignore lint/style/noParameterAssign: it is a reduce
    prev = Object.assign(Object.assign({}, prev), cur);
    return prev;
  }, {});
  return Object.assign(Object.assign(Object.assign(Object.assign(Object.assign(Object.assign(Object.assign({}, token), colorPalettes), (0, _genColorMapToken.default)(token, {
    generateColorPalettes: _colors2.generateColorPalettes,
    generateNeutralColorPalettes: _colors2.generateNeutralColorPalettes
  })), (0, _genFontMapToken.default)(token.fontSize)), (0, _genSizeMapToken.default)(token)), (0, _genControlHeight.default)(token)), (0, _genCommonMapToken.default)(token));
}