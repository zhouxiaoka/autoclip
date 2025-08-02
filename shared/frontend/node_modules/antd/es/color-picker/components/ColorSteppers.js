"use client";

import React, { useState } from 'react';
import classNames from 'classnames';
import InputNumber from '../../input-number';
const ColorSteppers = ({
  prefixCls,
  min = 0,
  max = 100,
  value,
  onChange,
  className,
  formatter
}) => {
  const colorSteppersPrefixCls = `${prefixCls}-steppers`;
  const [internalValue, setInternalValue] = useState(0);
  const stepValue = !Number.isNaN(value) ? value : internalValue;
  return /*#__PURE__*/React.createElement(InputNumber, {
    className: classNames(colorSteppersPrefixCls, className),
    min: min,
    max: max,
    value: stepValue,
    formatter: formatter,
    size: "small",
    onChange: step => {
      setInternalValue(step || 0);
      onChange === null || onChange === void 0 ? void 0 : onChange(step);
    }
  });
};
export default ColorSteppers;