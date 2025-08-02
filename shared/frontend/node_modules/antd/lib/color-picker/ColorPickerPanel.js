"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireDefault(require("react"));
var _divider = _interopRequireDefault(require("../divider"));
var _PanelPicker = _interopRequireDefault(require("./components/PanelPicker"));
var _PanelPresets = _interopRequireDefault(require("./components/PanelPresets"));
var _context = require("./context");
const ColorPickerPanel = props => {
  const {
    prefixCls,
    presets,
    panelRender,
    value,
    onChange,
    onClear,
    allowClear,
    disabledAlpha,
    mode,
    onModeChange,
    modeOptions,
    onChangeComplete,
    activeIndex,
    onActive,
    format,
    onFormatChange,
    gradientDragging,
    onGradientDragging,
    disabledFormat
  } = props;
  const colorPickerPanelPrefixCls = `${prefixCls}-inner`;
  // ===================== Context ======================
  const panelContext = _react.default.useMemo(() => ({
    prefixCls,
    value,
    onChange,
    onClear,
    allowClear,
    disabledAlpha,
    mode,
    onModeChange,
    modeOptions,
    onChangeComplete,
    activeIndex,
    onActive,
    format,
    onFormatChange,
    gradientDragging,
    onGradientDragging,
    disabledFormat
  }), [prefixCls, value, onChange, onClear, allowClear, disabledAlpha, mode, onModeChange, modeOptions, onChangeComplete, activeIndex, onActive, format, onFormatChange, gradientDragging, onGradientDragging, disabledFormat]);
  const presetContext = _react.default.useMemo(() => ({
    prefixCls,
    value,
    presets,
    onChange
  }), [prefixCls, value, presets, onChange]);
  // ====================== Render ======================
  const innerPanel = /*#__PURE__*/_react.default.createElement("div", {
    className: `${colorPickerPanelPrefixCls}-content`
  }, /*#__PURE__*/_react.default.createElement(_PanelPicker.default, null), Array.isArray(presets) && /*#__PURE__*/_react.default.createElement(_divider.default, null), /*#__PURE__*/_react.default.createElement(_PanelPresets.default, null));
  return /*#__PURE__*/_react.default.createElement(_context.PanelPickerContext.Provider, {
    value: panelContext
  }, /*#__PURE__*/_react.default.createElement(_context.PanelPresetsContext.Provider, {
    value: presetContext
  }, /*#__PURE__*/_react.default.createElement("div", {
    className: colorPickerPanelPrefixCls
  }, typeof panelRender === 'function' ? panelRender(innerPanel, {
    components: {
      Picker: _PanelPicker.default,
      Presets: _PanelPresets.default
    }
  }) : innerPanel)));
};
if (process.env.NODE_ENV !== 'production') {
  ColorPickerPanel.displayName = 'ColorPickerPanel';
}
var _default = exports.default = ColorPickerPanel;