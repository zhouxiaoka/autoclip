"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import React, { useContext } from 'react';
import classNames from 'classnames';
import omit from "rc-util/es/omit";
import convertToTooltipProps from '../_util/convertToTooltipProps';
import { useZIndex } from '../_util/hooks/useZIndex';
import { devUseWarning } from '../_util/warning';
import Badge from '../badge';
import { ConfigContext } from '../config-provider';
import useCSSVarCls from '../config-provider/hooks/useCSSVarCls';
import Tooltip from '../tooltip';
import FloatButtonGroupContext from './context';
import Content from './FloatButtonContent';
import useStyle from './style';
export const floatButtonPrefixCls = 'float-btn';
const InternalFloatButton = /*#__PURE__*/React.forwardRef((props, ref) => {
  const {
      prefixCls: customizePrefixCls,
      className,
      rootClassName,
      style,
      type = 'default',
      shape = 'circle',
      icon,
      description,
      tooltip,
      htmlType = 'button',
      badge = {}
    } = props,
    restProps = __rest(props, ["prefixCls", "className", "rootClassName", "style", "type", "shape", "icon", "description", "tooltip", "htmlType", "badge"]);
  const {
    getPrefixCls,
    direction
  } = useContext(ConfigContext);
  const groupShape = useContext(FloatButtonGroupContext);
  const prefixCls = getPrefixCls(floatButtonPrefixCls, customizePrefixCls);
  const rootCls = useCSSVarCls(prefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls, rootCls);
  const mergedShape = groupShape || shape;
  const classString = classNames(hashId, cssVarCls, rootCls, prefixCls, className, rootClassName, `${prefixCls}-${type}`, `${prefixCls}-${mergedShape}`, {
    [`${prefixCls}-rtl`]: direction === 'rtl'
  });
  // ============================ zIndex ============================
  const [zIndex] = useZIndex('FloatButton', style === null || style === void 0 ? void 0 : style.zIndex);
  const mergedStyle = Object.assign(Object.assign({}, style), {
    zIndex
  });
  // 虽然在 ts 中已经 omit 过了，但是为了防止多余的属性被透传进来，这里再 omit 一遍，以防万一
  const badgeProps = omit(badge, ['title', 'children', 'status', 'text']);
  let buttonNode = /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-body`
  }, /*#__PURE__*/React.createElement(Content, {
    prefixCls: prefixCls,
    description: description,
    icon: icon
  }));
  if ('badge' in props) {
    buttonNode = /*#__PURE__*/React.createElement(Badge, Object.assign({}, badgeProps), buttonNode);
  }
  // ============================ Tooltip ============================
  const tooltipProps = convertToTooltipProps(tooltip);
  if (tooltipProps) {
    buttonNode = /*#__PURE__*/React.createElement(Tooltip, Object.assign({}, tooltipProps), buttonNode);
  }
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('FloatButton');
    process.env.NODE_ENV !== "production" ? warning(!(shape === 'circle' && description), 'usage', 'supported only when `shape` is `square`. Due to narrow space for text, short sentence is recommended.') : void 0;
  }
  return wrapCSSVar(props.href ? (/*#__PURE__*/React.createElement("a", Object.assign({
    ref: ref
  }, restProps, {
    className: classString,
    style: mergedStyle
  }), buttonNode)) : (/*#__PURE__*/React.createElement("button", Object.assign({
    ref: ref
  }, restProps, {
    className: classString,
    style: mergedStyle,
    type: htmlType
  }), buttonNode)));
});
const FloatButton = InternalFloatButton;
if (process.env.NODE_ENV !== 'production') {
  FloatButton.displayName = 'FloatButton';
}
export default FloatButton;