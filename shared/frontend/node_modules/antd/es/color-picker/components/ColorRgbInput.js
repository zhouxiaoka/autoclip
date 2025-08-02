"use client";

import React, { useState } from 'react';
import { generateColor } from '../util';
import ColorSteppers from './ColorSteppers';
const ColorRgbInput = ({
  prefixCls,
  value,
  onChange
}) => {
  const colorRgbInputPrefixCls = `${prefixCls}-rgb-input`;
  const [internalValue, setInternalValue] = useState(() => generateColor(value || '#000'));
  const rgbValue = value || internalValue;
  const handleRgbChange = (step, type) => {
    const rgb = rgbValue.toRgb();
    rgb[type] = step || 0;
    const genColor = generateColor(rgb);
    setInternalValue(genColor);
    onChange === null || onChange === void 0 ? void 0 : onChange(genColor);
  };
  return /*#__PURE__*/React.createElement("div", {
    className: colorRgbInputPrefixCls
  }, /*#__PURE__*/React.createElement(ColorSteppers, {
    max: 255,
    min: 0,
    value: Number(rgbValue.toRgb().r),
    prefixCls: prefixCls,
    className: colorRgbInputPrefixCls,
    onChange: step => handleRgbChange(Number(step), 'r')
  }), /*#__PURE__*/React.createElement(ColorSteppers, {
    max: 255,
    min: 0,
    value: Number(rgbValue.toRgb().g),
    prefixCls: prefixCls,
    className: colorRgbInputPrefixCls,
    onChange: step => handleRgbChange(Number(step), 'g')
  }), /*#__PURE__*/React.createElement(ColorSteppers, {
    max: 255,
    min: 0,
    value: Number(rgbValue.toRgb().b),
    prefixCls: prefixCls,
    className: colorRgbInputPrefixCls,
    onChange: step => handleRgbChange(Number(step), 'b')
  }));
};
export default ColorRgbInput;