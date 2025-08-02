"use strict";
"use client";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireDefault(require("react"));
var _CloseOutlined = _interopRequireDefault(require("@ant-design/icons/CloseOutlined"));
var _FileTextOutlined = _interopRequireDefault(require("@ant-design/icons/FileTextOutlined"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcMotion = _interopRequireDefault(require("rc-motion"));
var _useEvent = _interopRequireDefault(require("rc-util/lib/hooks/useEvent"));
var _useMergedState = _interopRequireDefault(require("rc-util/lib/hooks/useMergedState"));
var _useZIndex = require("../_util/hooks/useZIndex");
var _warning = require("../_util/warning");
var _context = require("../config-provider/context");
var _useCSSVarCls = _interopRequireDefault(require("../config-provider/hooks/useCSSVarCls"));
var _context2 = require("./context");
var _FloatButton = _interopRequireWildcard(require("./FloatButton"));
var _style = _interopRequireDefault(require("./style"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const FloatButtonGroup = props => {
  var _a;
  const {
      prefixCls: customizePrefixCls,
      className,
      style,
      shape = 'circle',
      type = 'default',
      placement = 'top',
      icon = /*#__PURE__*/_react.default.createElement(_FileTextOutlined.default, null),
      closeIcon,
      description,
      trigger,
      children,
      onOpenChange,
      open: customOpen,
      onClick: onTriggerButtonClick
    } = props,
    floatButtonProps = __rest(props, ["prefixCls", "className", "style", "shape", "type", "placement", "icon", "closeIcon", "description", "trigger", "children", "onOpenChange", "open", "onClick"]);
  const {
    direction,
    getPrefixCls,
    closeIcon: contextCloseIcon
  } = (0, _context.useComponentConfig)('floatButtonGroup');
  const mergedCloseIcon = (_a = closeIcon !== null && closeIcon !== void 0 ? closeIcon : contextCloseIcon) !== null && _a !== void 0 ? _a : /*#__PURE__*/_react.default.createElement(_CloseOutlined.default, null);
  const prefixCls = getPrefixCls(_FloatButton.floatButtonPrefixCls, customizePrefixCls);
  const rootCls = (0, _useCSSVarCls.default)(prefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls, rootCls);
  const groupPrefixCls = `${prefixCls}-group`;
  const isMenuMode = trigger && ['click', 'hover'].includes(trigger);
  const isValidPlacement = placement && ['top', 'left', 'right', 'bottom'].includes(placement);
  const groupCls = (0, _classnames.default)(groupPrefixCls, hashId, cssVarCls, rootCls, className, {
    [`${groupPrefixCls}-rtl`]: direction === 'rtl',
    [`${groupPrefixCls}-${shape}`]: shape,
    [`${groupPrefixCls}-${shape}-shadow`]: !isMenuMode,
    [`${groupPrefixCls}-${placement}`]: isMenuMode && isValidPlacement // 只有菜单模式才支持弹出方向
  });
  // ============================ zIndex ============================
  const [zIndex] = (0, _useZIndex.useZIndex)('FloatButton', style === null || style === void 0 ? void 0 : style.zIndex);
  const mergedStyle = Object.assign(Object.assign({}, style), {
    zIndex
  });
  const wrapperCls = (0, _classnames.default)(hashId, `${groupPrefixCls}-wrap`);
  const [open, setOpen] = (0, _useMergedState.default)(false, {
    value: customOpen
  });
  const floatButtonGroupRef = _react.default.useRef(null);
  // ========================== Open ==========================
  const hoverTrigger = trigger === 'hover';
  const clickTrigger = trigger === 'click';
  const triggerOpen = (0, _useEvent.default)(nextOpen => {
    if (open !== nextOpen) {
      setOpen(nextOpen);
      onOpenChange === null || onOpenChange === void 0 ? void 0 : onOpenChange(nextOpen);
    }
  });
  // ===================== Trigger: Hover =====================
  const onMouseEnter = () => {
    if (hoverTrigger) {
      triggerOpen(true);
    }
  };
  const onMouseLeave = () => {
    if (hoverTrigger) {
      triggerOpen(false);
    }
  };
  // ===================== Trigger: Click =====================
  const onInternalTriggerButtonClick = e => {
    if (clickTrigger) {
      triggerOpen(!open);
    }
    onTriggerButtonClick === null || onTriggerButtonClick === void 0 ? void 0 : onTriggerButtonClick(e);
  };
  _react.default.useEffect(() => {
    if (clickTrigger) {
      const onDocClick = e => {
        var _a;
        // Skip if click on the group
        if ((_a = floatButtonGroupRef.current) === null || _a === void 0 ? void 0 : _a.contains(e.target)) {
          return;
        }
        triggerOpen(false);
      };
      document.addEventListener('click', onDocClick, {
        capture: true
      });
      return () => document.removeEventListener('click', onDocClick, {
        capture: true
      });
    }
  }, [clickTrigger]);
  // ======================== Warning =========================
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('FloatButton.Group');
    process.env.NODE_ENV !== "production" ? warning(!('open' in props) || !!trigger, 'usage', '`open` need to be used together with `trigger`') : void 0;
  }
  // ========================= Render =========================
  return wrapCSSVar(/*#__PURE__*/_react.default.createElement(_context2.FloatButtonGroupProvider, {
    value: shape
  }, /*#__PURE__*/_react.default.createElement("div", {
    ref: floatButtonGroupRef,
    className: groupCls,
    style: mergedStyle,
    // Hover trigger
    onMouseEnter: onMouseEnter,
    onMouseLeave: onMouseLeave
  }, isMenuMode ? (/*#__PURE__*/_react.default.createElement(_react.default.Fragment, null, /*#__PURE__*/_react.default.createElement(_rcMotion.default, {
    visible: open,
    motionName: `${groupPrefixCls}-wrap`
  }, ({
    className: motionClassName
  }) => (/*#__PURE__*/_react.default.createElement("div", {
    className: (0, _classnames.default)(motionClassName, wrapperCls)
  }, children))), /*#__PURE__*/_react.default.createElement(_FloatButton.default, Object.assign({
    type: type,
    icon: open ? mergedCloseIcon : icon,
    description: description,
    "aria-label": props['aria-label'],
    className: `${groupPrefixCls}-trigger`,
    onClick: onInternalTriggerButtonClick
  }, floatButtonProps)))) : children)));
};
var _default = exports.default = FloatButtonGroup;