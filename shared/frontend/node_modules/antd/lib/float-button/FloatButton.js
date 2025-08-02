"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.floatButtonPrefixCls = exports.default = void 0;
var _react = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _omit = _interopRequireDefault(require("rc-util/lib/omit"));
var _convertToTooltipProps = _interopRequireDefault(require("../_util/convertToTooltipProps"));
var _useZIndex = require("../_util/hooks/useZIndex");
var _warning = require("../_util/warning");
var _badge = _interopRequireDefault(require("../badge"));
var _configProvider = require("../config-provider");
var _useCSSVarCls = _interopRequireDefault(require("../config-provider/hooks/useCSSVarCls"));
var _tooltip = _interopRequireDefault(require("../tooltip"));
var _context = _interopRequireDefault(require("./context"));
var _FloatButtonContent = _interopRequireDefault(require("./FloatButtonContent"));
var _style = _interopRequireDefault(require("./style"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const floatButtonPrefixCls = exports.floatButtonPrefixCls = 'float-btn';
const InternalFloatButton = /*#__PURE__*/_react.default.forwardRef((props, ref) => {
  const {
      prefixCls: customizePrefixCls,
      className,
      rootClassName,
      style,
      type = 'default',
      shape = 'circle',
      icon,
      description,
      tooltip,
      htmlType = 'button',
      badge = {}
    } = props,
    restProps = __rest(props, ["prefixCls", "className", "rootClassName", "style", "type", "shape", "icon", "description", "tooltip", "htmlType", "badge"]);
  const {
    getPrefixCls,
    direction
  } = (0, _react.useContext)(_configProvider.ConfigContext);
  const groupShape = (0, _react.useContext)(_context.default);
  const prefixCls = getPrefixCls(floatButtonPrefixCls, customizePrefixCls);
  const rootCls = (0, _useCSSVarCls.default)(prefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls, rootCls);
  const mergedShape = groupShape || shape;
  const classString = (0, _classnames.default)(hashId, cssVarCls, rootCls, prefixCls, className, rootClassName, `${prefixCls}-${type}`, `${prefixCls}-${mergedShape}`, {
    [`${prefixCls}-rtl`]: direction === 'rtl'
  });
  // ============================ zIndex ============================
  const [zIndex] = (0, _useZIndex.useZIndex)('FloatButton', style === null || style === void 0 ? void 0 : style.zIndex);
  const mergedStyle = Object.assign(Object.assign({}, style), {
    zIndex
  });
  // 虽然在 ts 中已经 omit 过了，但是为了防止多余的属性被透传进来，这里再 omit 一遍，以防万一
  const badgeProps = (0, _omit.default)(badge, ['title', 'children', 'status', 'text']);
  let buttonNode = /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-body`
  }, /*#__PURE__*/_react.default.createElement(_FloatButtonContent.default, {
    prefixCls: prefixCls,
    description: description,
    icon: icon
  }));
  if ('badge' in props) {
    buttonNode = /*#__PURE__*/_react.default.createElement(_badge.default, Object.assign({}, badgeProps), buttonNode);
  }
  // ============================ Tooltip ============================
  const tooltipProps = (0, _convertToTooltipProps.default)(tooltip);
  if (tooltipProps) {
    buttonNode = /*#__PURE__*/_react.default.createElement(_tooltip.default, Object.assign({}, tooltipProps), buttonNode);
  }
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('FloatButton');
    process.env.NODE_ENV !== "production" ? warning(!(shape === 'circle' && description), 'usage', 'supported only when `shape` is `square`. Due to narrow space for text, short sentence is recommended.') : void 0;
  }
  return wrapCSSVar(props.href ? (/*#__PURE__*/_react.default.createElement("a", Object.assign({
    ref: ref
  }, restProps, {
    className: classString,
    style: mergedStyle
  }), buttonNode)) : (/*#__PURE__*/_react.default.createElement("button", Object.assign({
    ref: ref
  }, restProps, {
    className: classString,
    style: mergedStyle,
    type: htmlType
  }), buttonNode)));
});
const FloatButton = InternalFloatButton;
if (process.env.NODE_ENV !== 'production') {
  FloatButton.displayName = 'FloatButton';
}
var _default = exports.default = FloatButton;