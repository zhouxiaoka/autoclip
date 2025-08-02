"use strict";
"use client";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var _react = _interopRequireWildcard(require("react"));
var _colorPicker = _interopRequireDefault(require("@rc-component/color-picker"));
var _useLayoutEffect = _interopRequireDefault(require("rc-util/lib/hooks/useLayoutEffect"));
var _segmented = _interopRequireDefault(require("../../../segmented"));
var _color = require("../../color");
var _context = require("../../context");
var _util = require("../../util");
var _ColorClear = _interopRequireDefault(require("../ColorClear"));
var _ColorInput = _interopRequireDefault(require("../ColorInput"));
var _ColorSlider = _interopRequireDefault(require("../ColorSlider"));
var _GradientColorBar = _interopRequireDefault(require("./GradientColorBar"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const components = {
  slider: _ColorSlider.default
};
const PanelPicker = () => {
  const panelPickerContext = (0, _react.useContext)(_context.PanelPickerContext);
  const {
      mode,
      onModeChange,
      modeOptions,
      prefixCls,
      allowClear,
      value,
      disabledAlpha,
      onChange,
      onClear,
      onChangeComplete,
      activeIndex,
      gradientDragging
    } = panelPickerContext,
    injectProps = __rest(panelPickerContext, ["mode", "onModeChange", "modeOptions", "prefixCls", "allowClear", "value", "disabledAlpha", "onChange", "onClear", "onChangeComplete", "activeIndex", "gradientDragging"]);
  // ============================ Colors ============================
  const colors = _react.default.useMemo(() => {
    if (!value.cleared) {
      return value.getColors();
    }
    return [{
      percent: 0,
      color: new _color.AggregationColor('')
    }, {
      percent: 100,
      color: new _color.AggregationColor('')
    }];
  }, [value]);
  // ========================= Single Color =========================
  const isSingle = !value.isGradient();
  // We cache the point color in case user drag the gradient point across another one
  const [lockedColor, setLockedColor] = _react.default.useState(value);
  // Use layout effect here since `useEffect` will cause a blink when mouseDown
  (0, _useLayoutEffect.default)(() => {
    var _a;
    if (!isSingle) {
      setLockedColor((_a = colors[activeIndex]) === null || _a === void 0 ? void 0 : _a.color);
    }
  }, [gradientDragging, activeIndex]);
  const activeColor = _react.default.useMemo(() => {
    var _a;
    if (isSingle) {
      return value;
    }
    // Use cache when dragging. User can not operation panel when dragging.
    if (gradientDragging) {
      return lockedColor;
    }
    return (_a = colors[activeIndex]) === null || _a === void 0 ? void 0 : _a.color;
  }, [value, activeIndex, isSingle, lockedColor, gradientDragging]);
  // ========================= Picker Color =========================
  const [pickerColor, setPickerColor] = _react.default.useState(activeColor);
  const [forceSync, setForceSync] = _react.default.useState(0);
  const mergedPickerColor = (pickerColor === null || pickerColor === void 0 ? void 0 : pickerColor.equals(activeColor)) ? activeColor : pickerColor;
  (0, _useLayoutEffect.default)(() => {
    setPickerColor(activeColor);
  }, [forceSync, activeColor === null || activeColor === void 0 ? void 0 : activeColor.toHexString()]);
  // ============================ Change ============================
  const fillColor = (nextColor, info) => {
    let submitColor = (0, _util.generateColor)(nextColor);
    // Fill alpha color to 100% if origin is cleared color
    if (value.cleared) {
      const rgb = submitColor.toRgb();
      // Auto fill color if origin is `0/0/0` to enhance user experience
      if (!rgb.r && !rgb.g && !rgb.b && info) {
        const {
          type: infoType,
          value: infoValue = 0
        } = info;
        submitColor = new _color.AggregationColor({
          h: infoType === 'hue' ? infoValue : 0,
          s: 1,
          b: 1,
          a: infoType === 'alpha' ? infoValue / 100 : 1
        });
      } else {
        submitColor = (0, _util.genAlphaColor)(submitColor);
      }
    }
    if (mode === 'single') {
      return submitColor;
    }
    const nextColors = (0, _toConsumableArray2.default)(colors);
    nextColors[activeIndex] = Object.assign(Object.assign({}, nextColors[activeIndex]), {
      color: submitColor
    });
    return new _color.AggregationColor(nextColors);
  };
  const onPickerChange = (colorValue, fromPicker, info) => {
    const nextColor = fillColor(colorValue, info);
    setPickerColor(nextColor.isGradient() ? nextColor.getColors()[activeIndex].color : nextColor);
    onChange(nextColor, fromPicker);
  };
  const onInternalChangeComplete = (nextColor, info) => {
    // Trigger complete event
    onChangeComplete(fillColor(nextColor, info));
    // Back of origin color in case in controlled
    // This will set after `onChangeComplete` to avoid `setState` trigger rerender
    // which will make `fillColor` get wrong `color.cleared` state
    setForceSync(ori => ori + 1);
  };
  const onInputChange = colorValue => {
    onChange(fillColor(colorValue));
  };
  // ============================ Render ============================
  // Operation bar
  let operationNode = null;
  const showMode = modeOptions.length > 1;
  if (allowClear || showMode) {
    operationNode = /*#__PURE__*/_react.default.createElement("div", {
      className: `${prefixCls}-operation`
    }, showMode && (/*#__PURE__*/_react.default.createElement(_segmented.default, {
      size: "small",
      options: modeOptions,
      value: mode,
      onChange: onModeChange
    })), /*#__PURE__*/_react.default.createElement(_ColorClear.default, Object.assign({
      prefixCls: prefixCls,
      value: value,
      onChange: clearColor => {
        onChange(clearColor);
        onClear === null || onClear === void 0 ? void 0 : onClear();
      }
    }, injectProps)));
  }
  // Return
  return /*#__PURE__*/_react.default.createElement(_react.default.Fragment, null, operationNode, /*#__PURE__*/_react.default.createElement(_GradientColorBar.default, Object.assign({}, panelPickerContext, {
    colors: colors
  })), /*#__PURE__*/_react.default.createElement(_colorPicker.default, {
    prefixCls: prefixCls,
    value: mergedPickerColor === null || mergedPickerColor === void 0 ? void 0 : mergedPickerColor.toHsb(),
    disabledAlpha: disabledAlpha,
    onChange: (colorValue, info) => {
      onPickerChange(colorValue, true, info);
    },
    onChangeComplete: (colorValue, info) => {
      onInternalChangeComplete(colorValue, info);
    },
    components: components
  }), /*#__PURE__*/_react.default.createElement(_ColorInput.default, Object.assign({
    value: activeColor,
    onChange: onInputChange,
    prefixCls: prefixCls,
    disabledAlpha: disabledAlpha
  }, injectProps)));
};
var _default = exports.default = PanelPicker;