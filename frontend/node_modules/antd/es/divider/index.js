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
import { devUseWarning } from '../_util/warning';
import { useComponentConfig } from '../config-provider/context';
import useSize from '../config-provider/hooks/useSize';
import useStyle from './style';
const sizeClassNameMap = {
  small: 'sm',
  middle: 'md'
};
const Divider = props => {
  const {
    getPrefixCls,
    direction,
    className: dividerClassName,
    style: dividerStyle
  } = useComponentConfig('divider');
  const {
      prefixCls: customizePrefixCls,
      type = 'horizontal',
      orientation = 'center',
      orientationMargin,
      className,
      rootClassName,
      children,
      dashed,
      variant = 'solid',
      plain,
      style,
      size: customSize
    } = props,
    restProps = __rest(props, ["prefixCls", "type", "orientation", "orientationMargin", "className", "rootClassName", "children", "dashed", "variant", "plain", "style", "size"]);
  const prefixCls = getPrefixCls('divider', customizePrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls);
  const sizeFullName = useSize(customSize);
  const sizeCls = sizeClassNameMap[sizeFullName];
  const hasChildren = !!children;
  const mergedOrientation = React.useMemo(() => {
    if (orientation === 'left') {
      return direction === 'rtl' ? 'end' : 'start';
    }
    if (orientation === 'right') {
      return direction === 'rtl' ? 'start' : 'end';
    }
    return orientation;
  }, [direction, orientation]);
  const hasMarginStart = mergedOrientation === 'start' && orientationMargin != null;
  const hasMarginEnd = mergedOrientation === 'end' && orientationMargin != null;
  const classString = classNames(prefixCls, dividerClassName, hashId, cssVarCls, `${prefixCls}-${type}`, {
    [`${prefixCls}-with-text`]: hasChildren,
    [`${prefixCls}-with-text-${mergedOrientation}`]: hasChildren,
    [`${prefixCls}-dashed`]: !!dashed,
    [`${prefixCls}-${variant}`]: variant !== 'solid',
    [`${prefixCls}-plain`]: !!plain,
    [`${prefixCls}-rtl`]: direction === 'rtl',
    [`${prefixCls}-no-default-orientation-margin-start`]: hasMarginStart,
    [`${prefixCls}-no-default-orientation-margin-end`]: hasMarginEnd,
    [`${prefixCls}-${sizeCls}`]: !!sizeCls
  }, className, rootClassName);
  const memoizedOrientationMargin = React.useMemo(() => {
    if (typeof orientationMargin === 'number') {
      return orientationMargin;
    }
    if (/^\d+$/.test(orientationMargin)) {
      return Number(orientationMargin);
    }
    return orientationMargin;
  }, [orientationMargin]);
  const innerStyle = {
    marginInlineStart: hasMarginStart ? memoizedOrientationMargin : undefined,
    marginInlineEnd: hasMarginEnd ? memoizedOrientationMargin : undefined
  };
  // Warning children not work in vertical mode
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Divider');
    process.env.NODE_ENV !== "production" ? warning(!children || type !== 'vertical', 'usage', '`children` not working in `vertical` mode.') : void 0;
  }
  return wrapCSSVar(/*#__PURE__*/React.createElement("div", Object.assign({
    className: classString,
    style: Object.assign(Object.assign({}, dividerStyle), style)
  }, restProps, {
    role: "separator"
  }), children && type !== 'vertical' && (/*#__PURE__*/React.createElement("span", {
    className: `${prefixCls}-inner-text`,
    style: innerStyle
  }, children))));
};
if (process.env.NODE_ENV !== 'production') {
  Divider.displayName = 'Divider';
}
export default Divider;