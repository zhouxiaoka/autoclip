"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _classnames2 = _interopRequireDefault(require("classnames"));
var _react = _interopRequireDefault(require("react"));
var PanelContent = /*#__PURE__*/_react.default.forwardRef(function (props, ref) {
  var prefixCls = props.prefixCls,
    forceRender = props.forceRender,
    className = props.className,
    style = props.style,
    children = props.children,
    isActive = props.isActive,
    role = props.role,
    customizeClassNames = props.classNames,
    styles = props.styles;
  var _React$useState = _react.default.useState(isActive || forceRender),
    _React$useState2 = (0, _slicedToArray2.default)(_React$useState, 2),
    rendered = _React$useState2[0],
    setRendered = _React$useState2[1];
  _react.default.useEffect(function () {
    if (forceRender || isActive) {
      setRendered(true);
    }
  }, [forceRender, isActive]);
  if (!rendered) {
    return null;
  }
  return /*#__PURE__*/_react.default.createElement("div", {
    ref: ref,
    className: (0, _classnames2.default)("".concat(prefixCls, "-content"), (0, _defineProperty2.default)((0, _defineProperty2.default)({}, "".concat(prefixCls, "-content-active"), isActive), "".concat(prefixCls, "-content-inactive"), !isActive), className),
    style: style,
    role: role
  }, /*#__PURE__*/_react.default.createElement("div", {
    className: (0, _classnames2.default)("".concat(prefixCls, "-content-box"), customizeClassNames === null || customizeClassNames === void 0 ? void 0 : customizeClassNames.body),
    style: styles === null || styles === void 0 ? void 0 : styles.body
  }, children));
});
PanelContent.displayName = 'PanelContent';
var _default = exports.default = PanelContent;