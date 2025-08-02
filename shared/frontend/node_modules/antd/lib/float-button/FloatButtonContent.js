"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireWildcard(require("react"));
var _FileTextOutlined = _interopRequireDefault(require("@ant-design/icons/FileTextOutlined"));
var _classnames = _interopRequireDefault(require("classnames"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const FloatButtonContent = props => {
  const {
      icon,
      description,
      prefixCls,
      className
    } = props,
    rest = __rest(props, ["icon", "description", "prefixCls", "className"]);
  const defaultElement = /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-icon`
  }, /*#__PURE__*/_react.default.createElement(_FileTextOutlined.default, null));
  return /*#__PURE__*/_react.default.createElement("div", Object.assign({}, rest, {
    className: (0, _classnames.default)(className, `${prefixCls}-content`)
  }), icon || description ? (/*#__PURE__*/_react.default.createElement(_react.default.Fragment, null, icon && /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-icon`
  }, icon), description && /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-description`
  }, description))) : defaultElement);
};
var _default = exports.default = /*#__PURE__*/(0, _react.memo)(FloatButtonContent);