"use client";

import React, { useMemo } from 'react';
import useMergedState from "rc-util/es/hooks/useMergedState";
import Select from '../../select';
import { FORMAT_HEX, FORMAT_HSB, FORMAT_RGB } from '../interface';
import ColorAlphaInput from './ColorAlphaInput';
import ColorHexInput from './ColorHexInput';
import ColorHsbInput from './ColorHsbInput';
import ColorRgbInput from './ColorRgbInput';
const selectOptions = [FORMAT_HEX, FORMAT_HSB, FORMAT_RGB].map(format => ({
  value: format,
  label: format.toUpperCase()
}));
const ColorInput = props => {
  const {
    prefixCls,
    format,
    value,
    disabledAlpha,
    onFormatChange,
    onChange,
    disabledFormat
  } = props;
  const [colorFormat, setColorFormat] = useMergedState(FORMAT_HEX, {
    value: format,
    onChange: onFormatChange
  });
  const colorInputPrefixCls = `${prefixCls}-input`;
  const handleFormatChange = newFormat => {
    setColorFormat(newFormat);
  };
  const steppersNode = useMemo(() => {
    const inputProps = {
      value,
      prefixCls,
      onChange
    };
    switch (colorFormat) {
      case FORMAT_HSB:
        return /*#__PURE__*/React.createElement(ColorHsbInput, Object.assign({}, inputProps));
      case FORMAT_RGB:
        return /*#__PURE__*/React.createElement(ColorRgbInput, Object.assign({}, inputProps));
      // case FORMAT_HEX:
      default:
        return /*#__PURE__*/React.createElement(ColorHexInput, Object.assign({}, inputProps));
    }
  }, [colorFormat, prefixCls, value, onChange]);
  return /*#__PURE__*/React.createElement("div", {
    className: `${colorInputPrefixCls}-container`
  }, !disabledFormat && (/*#__PURE__*/React.createElement(Select, {
    value: colorFormat,
    variant: "borderless",
    getPopupContainer: current => current,
    popupMatchSelectWidth: 68,
    placement: "bottomRight",
    onChange: handleFormatChange,
    className: `${prefixCls}-format-select`,
    size: "small",
    options: selectOptions
  })), /*#__PURE__*/React.createElement("div", {
    className: colorInputPrefixCls
  }, steppersNode), !disabledAlpha && (/*#__PURE__*/React.createElement(ColorAlphaInput, {
    prefixCls: prefixCls,
    value: value,
    onChange: onChange
  })));
};
export default ColorInput;