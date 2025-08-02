"use client";

import React, { forwardRef } from 'react';
import LoadingOutlined from "@ant-design/icons/es/icons/LoadingOutlined";
import classNames from 'classnames';
import CSSMotion from 'rc-motion';
import IconWrapper from './IconWrapper';
const InnerLoadingIcon = /*#__PURE__*/forwardRef((props, ref) => {
  const {
    prefixCls,
    className,
    style,
    iconClassName
  } = props;
  const mergedIconCls = classNames(`${prefixCls}-loading-icon`, className);
  return /*#__PURE__*/React.createElement(IconWrapper, {
    prefixCls: prefixCls,
    className: mergedIconCls,
    style: style,
    ref: ref
  }, /*#__PURE__*/React.createElement(LoadingOutlined, {
    className: iconClassName
  }));
});
const getCollapsedWidth = () => ({
  width: 0,
  opacity: 0,
  transform: 'scale(0)'
});
const getRealWidth = node => ({
  width: node.scrollWidth,
  opacity: 1,
  transform: 'scale(1)'
});
const DefaultLoadingIcon = props => {
  const {
    prefixCls,
    loading,
    existIcon,
    className,
    style,
    mount
  } = props;
  const visible = !!loading;
  if (existIcon) {
    return /*#__PURE__*/React.createElement(InnerLoadingIcon, {
      prefixCls: prefixCls,
      className: className,
      style: style
    });
  }
  return /*#__PURE__*/React.createElement(CSSMotion, {
    visible: visible,
    // Used for minus flex gap style only
    motionName: `${prefixCls}-loading-icon-motion`,
    motionAppear: !mount,
    motionEnter: !mount,
    motionLeave: !mount,
    removeOnLeave: true,
    onAppearStart: getCollapsedWidth,
    onAppearActive: getRealWidth,
    onEnterStart: getCollapsedWidth,
    onEnterActive: getRealWidth,
    onLeaveStart: getRealWidth,
    onLeaveActive: getCollapsedWidth
  }, ({
    className: motionCls,
    style: motionStyle
  }, ref) => {
    const mergedStyle = Object.assign(Object.assign({}, style), motionStyle);
    return /*#__PURE__*/React.createElement(InnerLoadingIcon, {
      prefixCls: prefixCls,
      className: classNames(className, motionCls),
      style: mergedStyle,
      ref: ref
    });
  });
};
export default DefaultLoadingIcon;