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
import { responsiveArray } from '../_util/responsiveObserver';
import { ConfigContext } from '../config-provider';
import useBreakpoint from './hooks/useBreakpoint';
import useGutter from './hooks/useGutter';
import RowContext from './RowContext';
import { useRowStyle } from './style';
const _RowAligns = ['top', 'middle', 'bottom', 'stretch'];
const _RowJustify = ['start', 'end', 'center', 'space-around', 'space-between', 'space-evenly'];
function useMergedPropByScreen(oriProp, screen) {
  const [prop, setProp] = React.useState(typeof oriProp === 'string' ? oriProp : '');
  const calcMergedAlignOrJustify = () => {
    if (typeof oriProp === 'string') {
      setProp(oriProp);
    }
    if (typeof oriProp !== 'object') {
      return;
    }
    for (let i = 0; i < responsiveArray.length; i++) {
      const breakpoint = responsiveArray[i];
      // if do not match, do nothing
      if (!screen || !screen[breakpoint]) {
        continue;
      }
      const curVal = oriProp[breakpoint];
      if (curVal !== undefined) {
        setProp(curVal);
        return;
      }
    }
  };
  React.useEffect(() => {
    calcMergedAlignOrJustify();
  }, [JSON.stringify(oriProp), screen]);
  return prop;
}
const Row = /*#__PURE__*/React.forwardRef((props, ref) => {
  const {
      prefixCls: customizePrefixCls,
      justify,
      align,
      className,
      style,
      children,
      gutter = 0,
      wrap
    } = props,
    others = __rest(props, ["prefixCls", "justify", "align", "className", "style", "children", "gutter", "wrap"]);
  const {
    getPrefixCls,
    direction
  } = React.useContext(ConfigContext);
  const screens = useBreakpoint(true, null);
  const mergedAlign = useMergedPropByScreen(align, screens);
  const mergedJustify = useMergedPropByScreen(justify, screens);
  const prefixCls = getPrefixCls('row', customizePrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useRowStyle(prefixCls);
  const gutters = useGutter(gutter, screens);
  const classes = classNames(prefixCls, {
    [`${prefixCls}-no-wrap`]: wrap === false,
    [`${prefixCls}-${mergedJustify}`]: mergedJustify,
    [`${prefixCls}-${mergedAlign}`]: mergedAlign,
    [`${prefixCls}-rtl`]: direction === 'rtl'
  }, className, hashId, cssVarCls);
  // Add gutter related style
  const rowStyle = {};
  const horizontalGutter = gutters[0] != null && gutters[0] > 0 ? gutters[0] / -2 : undefined;
  if (horizontalGutter) {
    rowStyle.marginLeft = horizontalGutter;
    rowStyle.marginRight = horizontalGutter;
  }
  // "gutters" is a new array in each rendering phase, it'll make 'React.useMemo' effectless.
  // So we deconstruct "gutters" variable here.
  const [gutterH, gutterV] = gutters;
  rowStyle.rowGap = gutterV;
  const rowContext = React.useMemo(() => ({
    gutter: [gutterH, gutterV],
    wrap
  }), [gutterH, gutterV, wrap]);
  return wrapCSSVar(/*#__PURE__*/React.createElement(RowContext.Provider, {
    value: rowContext
  }, /*#__PURE__*/React.createElement("div", Object.assign({}, others, {
    className: classes,
    style: Object.assign(Object.assign({}, rowStyle), style),
    ref: ref
  }), children)));
});
if (process.env.NODE_ENV !== 'production') {
  Row.displayName = 'Row';
}
export default Row;