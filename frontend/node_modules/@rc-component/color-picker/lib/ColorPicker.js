"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _react = _interopRequireWildcard(require("react"));
var _util = require("./util");
var _classnames = _interopRequireDefault(require("classnames"));
var _color = require("./color");
var _ColorBlock = _interopRequireDefault(require("./components/ColorBlock"));
var _Picker = _interopRequireDefault(require("./components/Picker"));
var _useColorState3 = _interopRequireDefault(require("./hooks/useColorState"));
var _useComponent3 = _interopRequireDefault(require("./hooks/useComponent"));
var HUE_COLORS = [{
  color: 'rgb(255, 0, 0)',
  percent: 0
}, {
  color: 'rgb(255, 255, 0)',
  percent: 17
}, {
  color: 'rgb(0, 255, 0)',
  percent: 33
}, {
  color: 'rgb(0, 255, 255)',
  percent: 50
}, {
  color: 'rgb(0, 0, 255)',
  percent: 67
}, {
  color: 'rgb(255, 0, 255)',
  percent: 83
}, {
  color: 'rgb(255, 0, 0)',
  percent: 100
}];
var ColorPicker = /*#__PURE__*/(0, _react.forwardRef)(function (props, ref) {
  var value = props.value,
    defaultValue = props.defaultValue,
    _props$prefixCls = props.prefixCls,
    prefixCls = _props$prefixCls === void 0 ? _util.ColorPickerPrefixCls : _props$prefixCls,
    onChange = props.onChange,
    onChangeComplete = props.onChangeComplete,
    className = props.className,
    style = props.style,
    panelRender = props.panelRender,
    _props$disabledAlpha = props.disabledAlpha,
    disabledAlpha = _props$disabledAlpha === void 0 ? false : _props$disabledAlpha,
    _props$disabled = props.disabled,
    disabled = _props$disabled === void 0 ? false : _props$disabled,
    components = props.components;

  // ========================== Components ==========================
  var _useComponent = (0, _useComponent3.default)(components),
    _useComponent2 = (0, _slicedToArray2.default)(_useComponent, 1),
    Slider = _useComponent2[0];

  // ============================ Color =============================
  var _useColorState = (0, _useColorState3.default)(defaultValue || _util.defaultColor, value),
    _useColorState2 = (0, _slicedToArray2.default)(_useColorState, 2),
    colorValue = _useColorState2[0],
    setColorValue = _useColorState2[1];
  var alphaColor = (0, _react.useMemo)(function () {
    return colorValue.setA(1).toRgbString();
  }, [colorValue]);

  // ============================ Events ============================
  var handleChange = function handleChange(data, type) {
    if (!value) {
      setColorValue(data);
    }
    onChange === null || onChange === void 0 || onChange(data, type);
  };

  // Convert
  var getHueColor = function getHueColor(hue) {
    return new _color.Color(colorValue.setHue(hue));
  };
  var getAlphaColor = function getAlphaColor(alpha) {
    return new _color.Color(colorValue.setA(alpha / 100));
  };

  // Slider change
  var onHueChange = function onHueChange(hue) {
    handleChange(getHueColor(hue), {
      type: 'hue',
      value: hue
    });
  };
  var onAlphaChange = function onAlphaChange(alpha) {
    handleChange(getAlphaColor(alpha), {
      type: 'alpha',
      value: alpha
    });
  };

  // Complete
  var onHueChangeComplete = function onHueChangeComplete(hue) {
    if (onChangeComplete) {
      onChangeComplete(getHueColor(hue));
    }
  };
  var onAlphaChangeComplete = function onAlphaChangeComplete(alpha) {
    if (onChangeComplete) {
      onChangeComplete(getAlphaColor(alpha));
    }
  };

  // ============================ Render ============================
  var mergeCls = (0, _classnames.default)("".concat(prefixCls, "-panel"), className, (0, _defineProperty2.default)({}, "".concat(prefixCls, "-panel-disabled"), disabled));
  var sharedSliderProps = {
    prefixCls: prefixCls,
    disabled: disabled,
    color: colorValue
  };
  var defaultPanel = /*#__PURE__*/_react.default.createElement(_react.default.Fragment, null, /*#__PURE__*/_react.default.createElement(_Picker.default, (0, _extends2.default)({
    onChange: handleChange
  }, sharedSliderProps, {
    onChangeComplete: onChangeComplete
  })), /*#__PURE__*/_react.default.createElement("div", {
    className: "".concat(prefixCls, "-slider-container")
  }, /*#__PURE__*/_react.default.createElement("div", {
    className: (0, _classnames.default)("".concat(prefixCls, "-slider-group"), (0, _defineProperty2.default)({}, "".concat(prefixCls, "-slider-group-disabled-alpha"), disabledAlpha))
  }, /*#__PURE__*/_react.default.createElement(Slider, (0, _extends2.default)({}, sharedSliderProps, {
    type: "hue",
    colors: HUE_COLORS,
    min: 0,
    max: 359,
    value: colorValue.getHue(),
    onChange: onHueChange,
    onChangeComplete: onHueChangeComplete
  })), !disabledAlpha && /*#__PURE__*/_react.default.createElement(Slider, (0, _extends2.default)({}, sharedSliderProps, {
    type: "alpha",
    colors: [{
      percent: 0,
      color: 'rgba(255, 0, 4, 0)'
    }, {
      percent: 100,
      color: alphaColor
    }],
    min: 0,
    max: 100,
    value: colorValue.a * 100,
    onChange: onAlphaChange,
    onChangeComplete: onAlphaChangeComplete
  }))), /*#__PURE__*/_react.default.createElement(_ColorBlock.default, {
    color: colorValue.toRgbString(),
    prefixCls: prefixCls
  })));
  return /*#__PURE__*/_react.default.createElement("div", {
    className: mergeCls,
    style: style,
    ref: ref
  }, typeof panelRender === 'function' ? panelRender(defaultPanel) : defaultPanel);
});
if (process.env.NODE_ENV !== 'production') {
  ColorPicker.displayName = 'ColorPicker';
}
var _default = exports.default = ColorPicker;