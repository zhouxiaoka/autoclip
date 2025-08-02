"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _useMergedState = _interopRequireDefault(require("rc-util/lib/hooks/useMergedState"));
var _ContextIsolator = _interopRequireDefault(require("../_util/ContextIsolator"));
var _PurePanel = _interopRequireDefault(require("../_util/PurePanel"));
var _statusUtils = require("../_util/statusUtils");
var _warning = require("../_util/warning");
var _context = require("../config-provider/context");
var _DisabledContext = _interopRequireDefault(require("../config-provider/DisabledContext"));
var _useCSSVarCls = _interopRequireDefault(require("../config-provider/hooks/useCSSVarCls"));
var _useSize = _interopRequireDefault(require("../config-provider/hooks/useSize"));
var _context2 = require("../form/context");
var _popover = _interopRequireDefault(require("../popover"));
var _Compact = require("../space/Compact");
var _color = require("./color");
var _ColorPickerPanel = _interopRequireDefault(require("./ColorPickerPanel"));
var _ColorTrigger = _interopRequireDefault(require("./components/ColorTrigger"));
var _useModeColor = _interopRequireDefault(require("./hooks/useModeColor"));
var _style = _interopRequireDefault(require("./style"));
var _util = require("./util");
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const ColorPicker = props => {
  const {
      mode,
      value,
      defaultValue,
      format,
      defaultFormat,
      allowClear = false,
      presets,
      children,
      trigger = 'click',
      open,
      disabled,
      placement = 'bottomLeft',
      arrow = true,
      panelRender,
      showText,
      style,
      className,
      size: customizeSize,
      rootClassName,
      prefixCls: customizePrefixCls,
      styles,
      disabledAlpha = false,
      onFormatChange,
      onChange,
      onClear,
      onOpenChange,
      onChangeComplete,
      getPopupContainer,
      autoAdjustOverflow = true,
      destroyTooltipOnHide,
      destroyOnHidden,
      disabledFormat
    } = props,
    rest = __rest(props, ["mode", "value", "defaultValue", "format", "defaultFormat", "allowClear", "presets", "children", "trigger", "open", "disabled", "placement", "arrow", "panelRender", "showText", "style", "className", "size", "rootClassName", "prefixCls", "styles", "disabledAlpha", "onFormatChange", "onChange", "onClear", "onOpenChange", "onChangeComplete", "getPopupContainer", "autoAdjustOverflow", "destroyTooltipOnHide", "destroyOnHidden", "disabledFormat"]);
  const {
    getPrefixCls,
    direction,
    colorPicker
  } = (0, _react.useContext)(_context.ConfigContext);
  const contextDisabled = (0, _react.useContext)(_DisabledContext.default);
  const mergedDisabled = disabled !== null && disabled !== void 0 ? disabled : contextDisabled;
  const [popupOpen, setPopupOpen] = (0, _useMergedState.default)(false, {
    value: open,
    postState: openData => !mergedDisabled && openData,
    onChange: onOpenChange
  });
  const [formatValue, setFormatValue] = (0, _useMergedState.default)(format, {
    value: format,
    defaultValue: defaultFormat,
    onChange: onFormatChange
  });
  const prefixCls = getPrefixCls('color-picker', customizePrefixCls);
  // ================== Value & Mode =================
  const [mergedColor, setColor, modeState, setModeState, modeOptions] = (0, _useModeColor.default)(defaultValue, value, mode);
  const isAlphaColor = (0, _react.useMemo)(() => (0, _util.getColorAlpha)(mergedColor) < 100, [mergedColor]);
  // ==================== Change =====================
  // To enhance user experience, we cache the gradient color when switch from gradient to single
  // If user not modify single color, we will use the cached gradient color.
  const [cachedGradientColor, setCachedGradientColor] = _react.default.useState(null);
  const onInternalChangeComplete = color => {
    if (onChangeComplete) {
      let changeColor = (0, _util.generateColor)(color);
      // ignore alpha color
      if (disabledAlpha && isAlphaColor) {
        changeColor = (0, _util.genAlphaColor)(color);
      }
      onChangeComplete(changeColor);
    }
  };
  const onInternalChange = (data, changeFromPickerDrag) => {
    let color = (0, _util.generateColor)(data);
    // ignore alpha color
    if (disabledAlpha && isAlphaColor) {
      color = (0, _util.genAlphaColor)(color);
    }
    setColor(color);
    setCachedGradientColor(null);
    // Trigger change event
    if (onChange) {
      onChange(color, color.toCssString());
    }
    // Only for drag-and-drop color picking
    if (!changeFromPickerDrag) {
      onInternalChangeComplete(color);
    }
  };
  // =================== Gradient ====================
  const [activeIndex, setActiveIndex] = _react.default.useState(0);
  const [gradientDragging, setGradientDragging] = _react.default.useState(false);
  // Mode change should also trigger color change
  const onInternalModeChange = newMode => {
    setModeState(newMode);
    if (newMode === 'single' && mergedColor.isGradient()) {
      setActiveIndex(0);
      onInternalChange(new _color.AggregationColor(mergedColor.getColors()[0].color));
      // Should after `onInternalChange` since it will clear the cached color
      setCachedGradientColor(mergedColor);
    } else if (newMode === 'gradient' && !mergedColor.isGradient()) {
      const baseColor = isAlphaColor ? (0, _util.genAlphaColor)(mergedColor) : mergedColor;
      onInternalChange(new _color.AggregationColor(cachedGradientColor || [{
        percent: 0,
        color: baseColor
      }, {
        percent: 100,
        color: baseColor
      }]));
    }
  };
  // ================== Form Status ==================
  const {
    status: contextStatus
  } = _react.default.useContext(_context2.FormItemInputContext);
  // ==================== Compact ====================
  const {
    compactSize,
    compactItemClassnames
  } = (0, _Compact.useCompactItemContext)(prefixCls, direction);
  // ===================== Style =====================
  const mergedSize = (0, _useSize.default)(ctx => {
    var _a;
    return (_a = customizeSize !== null && customizeSize !== void 0 ? customizeSize : compactSize) !== null && _a !== void 0 ? _a : ctx;
  });
  const rootCls = (0, _useCSSVarCls.default)(prefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls, rootCls);
  const rtlCls = {
    [`${prefixCls}-rtl`]: direction
  };
  const mergedRootCls = (0, _classnames.default)(rootClassName, cssVarCls, rootCls, rtlCls);
  const mergedCls = (0, _classnames.default)((0, _statusUtils.getStatusClassNames)(prefixCls, contextStatus), {
    [`${prefixCls}-sm`]: mergedSize === 'small',
    [`${prefixCls}-lg`]: mergedSize === 'large'
  }, compactItemClassnames, colorPicker === null || colorPicker === void 0 ? void 0 : colorPicker.className, mergedRootCls, className, hashId);
  const mergedPopupCls = (0, _classnames.default)(prefixCls, mergedRootCls);
  // ===================== Warning ======================
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('ColorPicker');
    process.env.NODE_ENV !== "production" ? warning(!(disabledAlpha && isAlphaColor), 'usage', '`disabledAlpha` will make the alpha to be 100% when use alpha color.') : void 0;
  }
  const popoverProps = {
    open: popupOpen,
    trigger,
    placement,
    arrow,
    rootClassName,
    getPopupContainer,
    autoAdjustOverflow,
    destroyOnHidden: destroyOnHidden !== null && destroyOnHidden !== void 0 ? destroyOnHidden : !!destroyTooltipOnHide
  };
  const mergedStyle = Object.assign(Object.assign({}, colorPicker === null || colorPicker === void 0 ? void 0 : colorPicker.style), style);
  // ============================ zIndex ============================
  return wrapCSSVar(/*#__PURE__*/_react.default.createElement(_popover.default, Object.assign({
    style: styles === null || styles === void 0 ? void 0 : styles.popup,
    styles: {
      body: styles === null || styles === void 0 ? void 0 : styles.popupOverlayInner
    },
    onOpenChange: visible => {
      if (!visible || !mergedDisabled) {
        setPopupOpen(visible);
      }
    },
    content: /*#__PURE__*/_react.default.createElement(_ContextIsolator.default, {
      form: true
    }, /*#__PURE__*/_react.default.createElement(_ColorPickerPanel.default, {
      mode: modeState,
      onModeChange: onInternalModeChange,
      modeOptions: modeOptions,
      prefixCls: prefixCls,
      value: mergedColor,
      allowClear: allowClear,
      disabled: mergedDisabled,
      disabledAlpha: disabledAlpha,
      presets: presets,
      panelRender: panelRender,
      format: formatValue,
      onFormatChange: setFormatValue,
      onChange: onInternalChange,
      onChangeComplete: onInternalChangeComplete,
      onClear: onClear,
      activeIndex: activeIndex,
      onActive: setActiveIndex,
      gradientDragging: gradientDragging,
      onGradientDragging: setGradientDragging,
      disabledFormat: disabledFormat
    })),
    classNames: {
      root: mergedPopupCls
    }
  }, popoverProps), children || (/*#__PURE__*/_react.default.createElement(_ColorTrigger.default, Object.assign({
    activeIndex: popupOpen ? activeIndex : -1,
    open: popupOpen,
    className: mergedCls,
    style: mergedStyle,
    prefixCls: prefixCls,
    disabled: mergedDisabled,
    showText: showText,
    format: formatValue
  }, rest, {
    color: mergedColor
  })))));
};
if (process.env.NODE_ENV !== 'production') {
  ColorPicker.displayName = 'ColorPicker';
}
const PurePanel = (0, _PurePanel.default)(ColorPicker, undefined, props => Object.assign(Object.assign({}, props), {
  placement: 'bottom',
  autoAdjustOverflow: false
}), 'color-picker', /* istanbul ignore next */
prefixCls => prefixCls);
ColorPicker._InternalPanelDoNotUseOrYouWillBeFired = PurePanel;
var _default = exports.default = ColorPicker;