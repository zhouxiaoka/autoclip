"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import React, { memo } from 'react';
import FileTextOutlined from "@ant-design/icons/es/icons/FileTextOutlined";
import classNames from 'classnames';
const FloatButtonContent = props => {
  const {
      icon,
      description,
      prefixCls,
      className
    } = props,
    rest = __rest(props, ["icon", "description", "prefixCls", "className"]);
  const defaultElement = /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-icon`
  }, /*#__PURE__*/React.createElement(FileTextOutlined, null));
  return /*#__PURE__*/React.createElement("div", Object.assign({}, rest, {
    className: classNames(className, `${prefixCls}-content`)
  }), icon || description ? (/*#__PURE__*/React.createElement(React.Fragment, null, icon && /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-icon`
  }, icon), description && /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-description`
  }, description))) : defaultElement);
};
export default /*#__PURE__*/memo(FloatButtonContent);