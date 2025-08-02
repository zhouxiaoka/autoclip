"use client";

import * as React from 'react';
import { ConfigContext } from '../config-provider';
const BreadcrumbSeparator = ({
  children
}) => {
  const {
    getPrefixCls
  } = React.useContext(ConfigContext);
  const prefixCls = getPrefixCls('breadcrumb');
  return /*#__PURE__*/React.createElement("li", {
    className: `${prefixCls}-separator`,
    "aria-hidden": "true"
  }, children === '' ? children : children || '/');
};
BreadcrumbSeparator.__ANT_BREADCRUMB_SEPARATOR = true;
export default BreadcrumbSeparator;