"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _cssinjs = require("@ant-design/cssinjs");
const genPickerStyle = token => {
  const {
    componentCls,
    controlHeightLG,
    borderRadiusSM,
    colorPickerInsetShadow,
    marginSM,
    colorBgElevated,
    colorFillSecondary,
    lineWidthBold,
    colorPickerHandlerSize
  } = token;
  return {
    userSelect: 'none',
    [`${componentCls}-select`]: {
      [`${componentCls}-palette`]: {
        minHeight: token.calc(controlHeightLG).mul(4).equal(),
        overflow: 'hidden',
        borderRadius: borderRadiusSM
      },
      [`${componentCls}-saturation`]: {
        position: 'absolute',
        borderRadius: 'inherit',
        boxShadow: colorPickerInsetShadow,
        inset: 0
      },
      marginBottom: marginSM
    },
    // ======================== Panel =========================
    [`${componentCls}-handler`]: {
      width: colorPickerHandlerSize,
      height: colorPickerHandlerSize,
      border: `${(0, _cssinjs.unit)(lineWidthBold)} solid ${colorBgElevated}`,
      position: 'relative',
      borderRadius: '50%',
      cursor: 'pointer',
      boxShadow: `${colorPickerInsetShadow}, 0 0 0 1px ${colorFillSecondary}`
    }
  };
};
var _default = exports.default = genPickerStyle;