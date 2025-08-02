"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.getTransBg = exports.default = void 0;
var _cssinjs = require("@ant-design/cssinjs");
/**
 * @private Internal usage only
 * see: https://developer.mozilla.org/en-US/docs/Web/CSS/gradient/conic-gradient#checkerboard
 */
const getTransBg = (size, colorFill) => ({
  backgroundImage: `conic-gradient(${colorFill} 25%, transparent 25% 50%, ${colorFill} 50% 75%, transparent 75% 100%)`,
  backgroundSize: `${size} ${size}`
});
exports.getTransBg = getTransBg;
const genColorBlockStyle = (token, size) => {
  const {
    componentCls,
    borderRadiusSM,
    colorPickerInsetShadow,
    lineWidth,
    colorFillSecondary
  } = token;
  return {
    [`${componentCls}-color-block`]: Object.assign(Object.assign({
      position: 'relative',
      borderRadius: borderRadiusSM,
      width: size,
      height: size,
      boxShadow: colorPickerInsetShadow,
      flex: 'none'
    }, getTransBg('50%', token.colorFillSecondary)), {
      [`${componentCls}-color-block-inner`]: {
        width: '100%',
        height: '100%',
        boxShadow: `inset 0 0 0 ${(0, _cssinjs.unit)(lineWidth)} ${colorFillSecondary}`,
        borderRadius: 'inherit'
      }
    })
  };
};
var _default = exports.default = genColorBlockStyle;