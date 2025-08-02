"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import React, { forwardRef, useMemo } from 'react';
import { ColorBlock } from '@rc-component/color-picker';
import classNames from 'classnames';
import pickAttrs from "rc-util/es/pickAttrs";
import { useLocale } from '../../locale';
import { getColorAlpha } from '../util';
import ColorClear from './ColorClear';
const ColorTrigger = /*#__PURE__*/forwardRef((props, ref) => {
  const {
      color,
      prefixCls,
      open,
      disabled,
      format,
      className,
      showText,
      activeIndex
    } = props,
    rest = __rest(props, ["color", "prefixCls", "open", "disabled", "format", "className", "showText", "activeIndex"]);
  const colorTriggerPrefixCls = `${prefixCls}-trigger`;
  const colorTextPrefixCls = `${colorTriggerPrefixCls}-text`;
  const colorTextCellPrefixCls = `${colorTextPrefixCls}-cell`;
  const [locale] = useLocale('ColorPicker');
  // ============================== Text ==============================
  const desc = React.useMemo(() => {
    if (!showText) {
      return '';
    }
    if (typeof showText === 'function') {
      return showText(color);
    }
    if (color.cleared) {
      return locale.transparent;
    }
    if (color.isGradient()) {
      return color.getColors().map((c, index) => {
        const inactive = activeIndex !== -1 && activeIndex !== index;
        return /*#__PURE__*/React.createElement("span", {
          key: index,
          className: classNames(colorTextCellPrefixCls, inactive && `${colorTextCellPrefixCls}-inactive`)
        }, c.color.toRgbString(), " ", c.percent, "%");
      });
    }
    const hexString = color.toHexString().toUpperCase();
    const alpha = getColorAlpha(color);
    switch (format) {
      case 'rgb':
        return color.toRgbString();
      case 'hsb':
        return color.toHsbString();
      // case 'hex':
      default:
        return alpha < 100 ? `${hexString.slice(0, 7)},${alpha}%` : hexString;
    }
  }, [color, format, showText, activeIndex]);
  // ============================= Render =============================
  const containerNode = useMemo(() => color.cleared ? (/*#__PURE__*/React.createElement(ColorClear, {
    prefixCls: prefixCls
  })) : (/*#__PURE__*/React.createElement(ColorBlock, {
    prefixCls: prefixCls,
    color: color.toCssString()
  })), [color, prefixCls]);
  return /*#__PURE__*/React.createElement("div", Object.assign({
    ref: ref,
    className: classNames(colorTriggerPrefixCls, className, {
      [`${colorTriggerPrefixCls}-active`]: open,
      [`${colorTriggerPrefixCls}-disabled`]: disabled
    })
  }, pickAttrs(rest)), containerNode, showText && /*#__PURE__*/React.createElement("div", {
    className: colorTextPrefixCls
  }, desc));
});
export default ColorTrigger;