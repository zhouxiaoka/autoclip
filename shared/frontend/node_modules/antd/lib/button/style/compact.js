"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _compactItem = require("../../style/compact-item");
var _compactItemVertical = require("../../style/compact-item-vertical");
var _internal = require("../../theme/internal");
var _token = require("./token");
const genButtonCompactStyle = token => {
  const {
    componentCls,
    colorPrimaryHover,
    lineWidth,
    calc
  } = token;
  const insetOffset = calc(lineWidth).mul(-1).equal();
  const getCompactBorderStyle = vertical => {
    const selector = `${componentCls}-compact${vertical ? '-vertical' : ''}-item${componentCls}-primary:not([disabled])`;
    return {
      [`${selector} + ${selector}::before`]: {
        position: 'absolute',
        top: vertical ? insetOffset : 0,
        insetInlineStart: vertical ? 0 : insetOffset,
        backgroundColor: colorPrimaryHover,
        content: '""',
        width: vertical ? '100%' : lineWidth,
        height: vertical ? lineWidth : '100%'
      }
    };
  };
  // Special styles for Primary Button
  return Object.assign(Object.assign({}, getCompactBorderStyle()), getCompactBorderStyle(true));
};
// ============================== Export ==============================
var _default = exports.default = (0, _internal.genSubStyleComponent)(['Button', 'compact'], token => {
  const buttonToken = (0, _token.prepareToken)(token);
  return [
  // Space Compact
  (0, _compactItem.genCompactItemStyle)(buttonToken), (0, _compactItemVertical.genCompactItemVerticalStyle)(buttonToken), genButtonCompactStyle(buttonToken)];
}, _token.prepareComponentToken);