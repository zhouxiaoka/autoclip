"use client";

import * as React from 'react';
import classNames from 'classnames';
import toArray from "rc-util/es/Children/toArray";
import { cloneElement } from '../_util/reactNode';
import { devUseWarning } from '../_util/warning';
import { ConfigContext } from '../config-provider';
import useCSSVarCls from '../config-provider/hooks/useCSSVarCls';
import Popover from '../popover';
import Avatar from './Avatar';
import AvatarContext from './AvatarContext';
import useStyle from './style';
const AvatarContextProvider = props => {
  const {
    size,
    shape
  } = React.useContext(AvatarContext);
  const avatarContextValue = React.useMemo(() => ({
    size: props.size || size,
    shape: props.shape || shape
  }), [props.size, props.shape, size, shape]);
  return /*#__PURE__*/React.createElement(AvatarContext.Provider, {
    value: avatarContextValue
  }, props.children);
};
const AvatarGroup = props => {
  var _a, _b, _c, _d;
  const {
    getPrefixCls,
    direction
  } = React.useContext(ConfigContext);
  const {
    prefixCls: customizePrefixCls,
    className,
    rootClassName,
    style,
    maxCount,
    maxStyle,
    size,
    shape,
    maxPopoverPlacement,
    maxPopoverTrigger,
    children,
    max
  } = props;
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Avatar.Group');
    [['maxCount', 'max={{ count: number }}'], ['maxStyle', 'max={{ style: CSSProperties }}'], ['maxPopoverPlacement', 'max={{ popover: PopoverProps }}'], ['maxPopoverTrigger', 'max={{ popover: PopoverProps }}']].forEach(([deprecatedName, newName]) => {
      warning.deprecated(!(deprecatedName in props), deprecatedName, newName);
    });
  }
  const prefixCls = getPrefixCls('avatar', customizePrefixCls);
  const groupPrefixCls = `${prefixCls}-group`;
  const rootCls = useCSSVarCls(prefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls, rootCls);
  const cls = classNames(groupPrefixCls, {
    [`${groupPrefixCls}-rtl`]: direction === 'rtl'
  }, cssVarCls, rootCls, className, rootClassName, hashId);
  const childrenWithProps = toArray(children).map((child, index) => cloneElement(child, {
    // eslint-disable-next-line react/no-array-index-key
    key: `avatar-key-${index}`
  }));
  const mergeCount = (max === null || max === void 0 ? void 0 : max.count) || maxCount;
  const numOfChildren = childrenWithProps.length;
  if (mergeCount && mergeCount < numOfChildren) {
    const childrenShow = childrenWithProps.slice(0, mergeCount);
    const childrenHidden = childrenWithProps.slice(mergeCount, numOfChildren);
    const mergeStyle = (max === null || max === void 0 ? void 0 : max.style) || maxStyle;
    const mergePopoverTrigger = ((_a = max === null || max === void 0 ? void 0 : max.popover) === null || _a === void 0 ? void 0 : _a.trigger) || maxPopoverTrigger || 'hover';
    const mergePopoverPlacement = ((_b = max === null || max === void 0 ? void 0 : max.popover) === null || _b === void 0 ? void 0 : _b.placement) || maxPopoverPlacement || 'top';
    const mergeProps = Object.assign(Object.assign({
      content: childrenHidden
    }, max === null || max === void 0 ? void 0 : max.popover), {
      classNames: {
        root: classNames(`${groupPrefixCls}-popover`, (_d = (_c = max === null || max === void 0 ? void 0 : max.popover) === null || _c === void 0 ? void 0 : _c.classNames) === null || _d === void 0 ? void 0 : _d.root)
      },
      placement: mergePopoverPlacement,
      trigger: mergePopoverTrigger
    });
    childrenShow.push(/*#__PURE__*/React.createElement(Popover, Object.assign({
      key: "avatar-popover-key",
      destroyOnHidden: true
    }, mergeProps), /*#__PURE__*/React.createElement(Avatar, {
      style: mergeStyle
    }, `+${numOfChildren - mergeCount}`)));
    return wrapCSSVar(/*#__PURE__*/React.createElement(AvatarContextProvider, {
      shape: shape,
      size: size
    }, /*#__PURE__*/React.createElement("div", {
      className: cls,
      style: style
    }, childrenShow)));
  }
  return wrapCSSVar(/*#__PURE__*/React.createElement(AvatarContextProvider, {
    shape: shape,
    size: size
  }, /*#__PURE__*/React.createElement("div", {
    className: cls,
    style: style
  }, childrenWithProps)));
};
export default AvatarGroup;