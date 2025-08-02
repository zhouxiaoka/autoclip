"use client";

import React from 'react';
import { ReloadOutlined } from '@ant-design/icons';
import Button from '../button';
import Spin from '../spin';
const defaultSpin = /*#__PURE__*/React.createElement(Spin, null);
export default function QRcodeStatus({
  prefixCls,
  locale,
  onRefresh,
  statusRender,
  status
}) {
  const defaultExpiredNode = /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
    className: `${prefixCls}-expired`
  }, locale === null || locale === void 0 ? void 0 : locale.expired), onRefresh && (/*#__PURE__*/React.createElement(Button, {
    type: "link",
    icon: /*#__PURE__*/React.createElement(ReloadOutlined, null),
    onClick: onRefresh
  }, locale === null || locale === void 0 ? void 0 : locale.refresh)));
  const defaultScannedNode = /*#__PURE__*/React.createElement("p", {
    className: `${prefixCls}-scanned`
  }, locale === null || locale === void 0 ? void 0 : locale.scanned);
  const defaultNodes = {
    expired: defaultExpiredNode,
    loading: defaultSpin,
    scanned: defaultScannedNode
  };
  const defaultStatusRender = info => defaultNodes[info.status];
  const mergedStatusRender = statusRender !== null && statusRender !== void 0 ? statusRender : defaultStatusRender;
  return mergedStatusRender({
    status,
    locale,
    onRefresh
  });
}