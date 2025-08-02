"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _rcSelect = require("rc-select");
var React = _interopRequireWildcard(require("react"));
var _List = _interopRequireDefault(require("./List"));
var RefOptionList = /*#__PURE__*/React.forwardRef(function (props, ref) {
  var baseProps = (0, _rcSelect.useBaseProps)();

  // >>>>> Render
  return /*#__PURE__*/React.createElement(_List.default, (0, _extends2.default)({}, props, baseProps, {
    ref: ref
  }));
});
var _default = exports.default = RefOptionList;