"use client";

import React, { useState } from 'react';
import { generateColor, getColorAlpha } from '../util';
import ColorSteppers from './ColorSteppers';
const ColorAlphaInput = ({
  prefixCls,
  value,
  onChange
}) => {
  const colorAlphaInputPrefixCls = `${prefixCls}-alpha-input`;
  const [internalValue, setInternalValue] = useState(() => generateColor(value || '#000'));
  const alphaValue = value || internalValue;
  const handleAlphaChange = step => {
    const hsba = alphaValue.toHsb();
    hsba.a = (step || 0) / 100;
    const genColor = generateColor(hsba);
    setInternalValue(genColor);
    onChange === null || onChange === void 0 ? void 0 : onChange(genColor);
  };
  return /*#__PURE__*/React.createElement(ColorSteppers, {
    value: getColorAlpha(alphaValue),
    prefixCls: prefixCls,
    formatter: step => `${step}%`,
    className: colorAlphaInputPrefixCls,
    onChange: handleAlphaChange
  });
};
export default ColorAlphaInput;