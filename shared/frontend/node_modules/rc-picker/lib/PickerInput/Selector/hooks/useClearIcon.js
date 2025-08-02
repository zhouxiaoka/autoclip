"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.fillClearIcon = fillClearIcon;
var _typeof2 = _interopRequireDefault(require("@babel/runtime/helpers/typeof"));
var _warning = _interopRequireDefault(require("rc-util/lib/warning"));
var React = _interopRequireWildcard(require("react"));
/**
 * Used for `useFilledProps` since it already in the React.useMemo
 */
function fillClearIcon(prefixCls, allowClear, clearIcon) {
  if (process.env.NODE_ENV !== 'production' && clearIcon) {
    (0, _warning.default)(false, '`clearIcon` will be removed in future. Please use `allowClear` instead.');
  }
  if (allowClear === false) {
    return null;
  }
  var config = allowClear && (0, _typeof2.default)(allowClear) === 'object' ? allowClear : {};
  return config.clearIcon || clearIcon || /*#__PURE__*/React.createElement("span", {
    className: "".concat(prefixCls, "-clear-btn")
  });
}