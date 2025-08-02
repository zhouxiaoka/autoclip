"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = require("react");
function convertToTooltipProps(tooltip) {
  // isNil
  if (tooltip === undefined || tooltip === null) {
    return null;
  }
  if (typeof tooltip === 'object' && ! /*#__PURE__*/(0, _react.isValidElement)(tooltip)) {
    return tooltip;
  }
  return {
    title: tooltip
  };
}
var _default = exports.default = convertToTooltipProps;