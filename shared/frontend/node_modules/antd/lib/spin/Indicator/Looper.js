"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = Looper;
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _Progress = _interopRequireDefault(require("./Progress"));
function Looper(props) {
  const {
    prefixCls,
    percent = 0
  } = props;
  const dotClassName = `${prefixCls}-dot`;
  const holderClassName = `${dotClassName}-holder`;
  const hideClassName = `${holderClassName}-hidden`;
  // ===================== Render =====================
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
    className: (0, _classnames.default)(holderClassName, percent > 0 && hideClassName)
  }, /*#__PURE__*/React.createElement("span", {
    className: (0, _classnames.default)(dotClassName, `${prefixCls}-dot-spin`)
  }, [1, 2, 3, 4].map(i => (/*#__PURE__*/React.createElement("i", {
    className: `${prefixCls}-dot-item`,
    key: i
  }))))), /*#__PURE__*/React.createElement(_Progress.default, {
    prefixCls: prefixCls,
    percent: percent
  }));
}