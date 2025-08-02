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
import { useContext, useEffect, useRef, useState } from 'react';
import BarsOutlined from "@ant-design/icons/es/icons/BarsOutlined";
import LeftOutlined from "@ant-design/icons/es/icons/LeftOutlined";
import RightOutlined from "@ant-design/icons/es/icons/RightOutlined";
import classNames from 'classnames';
import omit from "rc-util/es/omit";
import { addMediaQueryListener, removeMediaQueryListener } from '../_util/mediaQueryUtil';
import { ConfigContext } from '../config-provider';
import { LayoutContext } from './context';
import useStyle from './style/sider';
const dimensionMaxMap = {
  xs: '479.98px',
  sm: '575.98px',
  md: '767.98px',
  lg: '991.98px',
  xl: '1199.98px',
  xxl: '1599.98px'
};
const isNumeric = value => !Number.isNaN(Number.parseFloat(value)) && isFinite(value);
export const SiderContext = /*#__PURE__*/React.createContext({});
const generateId = (() => {
  let i = 0;
  return (prefix = '') => {
    i += 1;
    return `${prefix}${i}`;
  };
})();
const Sider = /*#__PURE__*/React.forwardRef((props, ref) => {
  const {
      prefixCls: customizePrefixCls,
      className,
      trigger,
      children,
      defaultCollapsed = false,
      theme = 'dark',
      style = {},
      collapsible = false,
      reverseArrow = false,
      width = 200,
      collapsedWidth = 80,
      zeroWidthTriggerStyle,
      breakpoint,
      onCollapse,
      onBreakpoint
    } = props,
    otherProps = __rest(props, ["prefixCls", "className", "trigger", "children", "defaultCollapsed", "theme", "style", "collapsible", "reverseArrow", "width", "collapsedWidth", "zeroWidthTriggerStyle", "breakpoint", "onCollapse", "onBreakpoint"]);
  const {
    siderHook
  } = useContext(LayoutContext);
  const [collapsed, setCollapsed] = useState('collapsed' in props ? props.collapsed : defaultCollapsed);
  const [below, setBelow] = useState(false);
  useEffect(() => {
    if ('collapsed' in props) {
      setCollapsed(props.collapsed);
    }
  }, [props.collapsed]);
  const handleSetCollapsed = (value, type) => {
    if (!('collapsed' in props)) {
      setCollapsed(value);
    }
    onCollapse === null || onCollapse === void 0 ? void 0 : onCollapse(value, type);
  };
  // =========================== Prefix ===========================
  const {
    getPrefixCls,
    direction
  } = useContext(ConfigContext);
  const prefixCls = getPrefixCls('layout-sider', customizePrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls);
  // ========================= Responsive =========================
  const responsiveHandlerRef = useRef(null);
  responsiveHandlerRef.current = mql => {
    setBelow(mql.matches);
    onBreakpoint === null || onBreakpoint === void 0 ? void 0 : onBreakpoint(mql.matches);
    if (collapsed !== mql.matches) {
      handleSetCollapsed(mql.matches, 'responsive');
    }
  };
  useEffect(() => {
    function responsiveHandler(mql) {
      var _a;
      return (_a = responsiveHandlerRef.current) === null || _a === void 0 ? void 0 : _a.call(responsiveHandlerRef, mql);
    }
    let mql;
    if (typeof (window === null || window === void 0 ? void 0 : window.matchMedia) !== 'undefined' && breakpoint && breakpoint in dimensionMaxMap) {
      mql = window.matchMedia(`screen and (max-width: ${dimensionMaxMap[breakpoint]})`);
      addMediaQueryListener(mql, responsiveHandler);
      responsiveHandler(mql);
    }
    return () => {
      removeMediaQueryListener(mql, responsiveHandler);
    };
  }, [breakpoint]); // in order to accept dynamic 'breakpoint' property, we need to add 'breakpoint' into dependency array.
  useEffect(() => {
    const uniqueId = generateId('ant-sider-');
    siderHook.addSider(uniqueId);
    return () => siderHook.removeSider(uniqueId);
  }, []);
  const toggle = () => {
    handleSetCollapsed(!collapsed, 'clickTrigger');
  };
  const divProps = omit(otherProps, ['collapsed']);
  const rawWidth = collapsed ? collapsedWidth : width;
  // use "px" as fallback unit for width
  const siderWidth = isNumeric(rawWidth) ? `${rawWidth}px` : String(rawWidth);
  // special trigger when collapsedWidth == 0
  const zeroWidthTrigger = parseFloat(String(collapsedWidth || 0)) === 0 ? (/*#__PURE__*/React.createElement("span", {
    onClick: toggle,
    className: classNames(`${prefixCls}-zero-width-trigger`, `${prefixCls}-zero-width-trigger-${reverseArrow ? 'right' : 'left'}`),
    style: zeroWidthTriggerStyle
  }, trigger || /*#__PURE__*/React.createElement(BarsOutlined, null))) : null;
  const reverseIcon = direction === 'rtl' === !reverseArrow;
  const iconObj = {
    expanded: reverseIcon ? /*#__PURE__*/React.createElement(RightOutlined, null) : /*#__PURE__*/React.createElement(LeftOutlined, null),
    collapsed: reverseIcon ? /*#__PURE__*/React.createElement(LeftOutlined, null) : /*#__PURE__*/React.createElement(RightOutlined, null)
  };
  const status = collapsed ? 'collapsed' : 'expanded';
  const defaultTrigger = iconObj[status];
  const triggerDom = trigger !== null ? zeroWidthTrigger || (/*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-trigger`,
    onClick: toggle,
    style: {
      width: siderWidth
    }
  }, trigger || defaultTrigger)) : null;
  const divStyle = Object.assign(Object.assign({}, style), {
    flex: `0 0 ${siderWidth}`,
    maxWidth: siderWidth,
    minWidth: siderWidth,
    width: siderWidth
  });
  const siderCls = classNames(prefixCls, `${prefixCls}-${theme}`, {
    [`${prefixCls}-collapsed`]: !!collapsed,
    [`${prefixCls}-has-trigger`]: collapsible && trigger !== null && !zeroWidthTrigger,
    [`${prefixCls}-below`]: !!below,
    [`${prefixCls}-zero-width`]: parseFloat(siderWidth) === 0
  }, className, hashId, cssVarCls);
  const contextValue = React.useMemo(() => ({
    siderCollapsed: collapsed
  }), [collapsed]);
  return wrapCSSVar(/*#__PURE__*/React.createElement(SiderContext.Provider, {
    value: contextValue
  }, /*#__PURE__*/React.createElement("aside", Object.assign({
    className: siderCls
  }, divProps, {
    style: divStyle,
    ref: ref
  }), /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-children`
  }, children), collapsible || below && zeroWidthTrigger ? triggerDom : null)));
});
if (process.env.NODE_ENV !== 'production') {
  Sider.displayName = 'Sider';
}
export default Sider;