"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import * as React from 'react';
import classNames from 'classnames';
import pickAttrs from "rc-util/es/pickAttrs";
import { useComponentConfig } from '../config-provider/context';
import Skeleton from '../skeleton';
import StatisticNumber from './Number';
import useStyle from './style';
const Statistic = /*#__PURE__*/React.forwardRef((props, ref) => {
  const {
      prefixCls: customizePrefixCls,
      className,
      rootClassName,
      style,
      valueStyle,
      value = 0,
      title,
      valueRender,
      prefix,
      suffix,
      loading = false,
      /* --- FormatConfig starts --- */
      formatter,
      precision,
      decimalSeparator = '.',
      groupSeparator = ',',
      /* --- FormatConfig starts --- */
      onMouseEnter,
      onMouseLeave
    } = props,
    rest = __rest(props, ["prefixCls", "className", "rootClassName", "style", "valueStyle", "value", "title", "valueRender", "prefix", "suffix", "loading", "formatter", "precision", "decimalSeparator", "groupSeparator", "onMouseEnter", "onMouseLeave"]);
  const {
    getPrefixCls,
    direction,
    className: contextClassName,
    style: contextStyle
  } = useComponentConfig('statistic');
  const prefixCls = getPrefixCls('statistic', customizePrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls);
  const valueNode = /*#__PURE__*/React.createElement(StatisticNumber, {
    decimalSeparator: decimalSeparator,
    groupSeparator: groupSeparator,
    prefixCls: prefixCls,
    formatter: formatter,
    precision: precision,
    value: value
  });
  const cls = classNames(prefixCls, {
    [`${prefixCls}-rtl`]: direction === 'rtl'
  }, contextClassName, className, rootClassName, hashId, cssVarCls);
  const internalRef = React.useRef(null);
  React.useImperativeHandle(ref, () => ({
    nativeElement: internalRef.current
  }));
  const restProps = pickAttrs(rest, {
    aria: true,
    data: true
  });
  return wrapCSSVar(/*#__PURE__*/React.createElement("div", Object.assign({}, restProps, {
    ref: internalRef,
    className: cls,
    style: Object.assign(Object.assign({}, contextStyle), style),
    onMouseEnter: onMouseEnter,
    onMouseLeave: onMouseLeave
  }), title && /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-title`
  }, title), /*#__PURE__*/React.createElement(Skeleton, {
    paragraph: false,
    loading: loading,
    className: `${prefixCls}-skeleton`
  }, /*#__PURE__*/React.createElement("div", {
    style: valueStyle,
    className: `${prefixCls}-content`
  }, prefix && /*#__PURE__*/React.createElement("span", {
    className: `${prefixCls}-content-prefix`
  }, prefix), valueRender ? valueRender(valueNode) : valueNode, suffix && /*#__PURE__*/React.createElement("span", {
    className: `${prefixCls}-content-suffix`
  }, suffix)))));
});
if (process.env.NODE_ENV !== 'production') {
  Statistic.displayName = 'Statistic';
}
export default Statistic;