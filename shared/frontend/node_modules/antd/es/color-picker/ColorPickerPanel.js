"use client";

import React from 'react';
import Divider from '../divider';
import PanelPicker from './components/PanelPicker';
import PanelPresets from './components/PanelPresets';
import { PanelPickerContext, PanelPresetsContext } from './context';
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
  const panelContext = React.useMemo(() => ({
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
  const presetContext = React.useMemo(() => ({
    prefixCls,
    value,
    presets,
    onChange
  }), [prefixCls, value, presets, onChange]);
  // ====================== Render ======================
  const innerPanel = /*#__PURE__*/React.createElement("div", {
    className: `${colorPickerPanelPrefixCls}-content`
  }, /*#__PURE__*/React.createElement(PanelPicker, null), Array.isArray(presets) && /*#__PURE__*/React.createElement(Divider, null), /*#__PURE__*/React.createElement(PanelPresets, null));
  return /*#__PURE__*/React.createElement(PanelPickerContext.Provider, {
    value: panelContext
  }, /*#__PURE__*/React.createElement(PanelPresetsContext.Provider, {
    value: presetContext
  }, /*#__PURE__*/React.createElement("div", {
    className: colorPickerPanelPrefixCls
  }, typeof panelRender === 'function' ? panelRender(innerPanel, {
    components: {
      Picker: PanelPicker,
      Presets: PanelPresets
    }
  }) : innerPanel)));
};
if (process.env.NODE_ENV !== 'production') {
  ColorPickerPanel.displayName = 'ColorPickerPanel';
}
export default ColorPickerPanel;