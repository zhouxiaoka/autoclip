"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.prepareComponentToken = void 0;
var _fastColor = require("@ant-design/fast-color");
var _token = require("../../input/style/token");
const prepareComponentToken = token => {
  var _a;
  const handleVisible = (_a = token.handleVisible) !== null && _a !== void 0 ? _a : 'auto';
  const handleWidth = token.controlHeightSM - token.lineWidth * 2;
  return Object.assign(Object.assign({}, (0, _token.initComponentToken)(token)), {
    controlWidth: 90,
    handleWidth,
    handleFontSize: token.fontSize / 2,
    handleVisible,
    handleActiveBg: token.colorFillAlter,
    handleBg: token.colorBgContainer,
    filledHandleBg: new _fastColor.FastColor(token.colorFillSecondary).onBackground(token.colorBgContainer).toHexString(),
    handleHoverColor: token.colorPrimary,
    handleBorderColor: token.colorBorder,
    handleOpacity: handleVisible === true ? 1 : 0,
    handleVisibleWidth: handleVisible === true ? handleWidth : 0
  });
};
exports.prepareComponentToken = prepareComponentToken;