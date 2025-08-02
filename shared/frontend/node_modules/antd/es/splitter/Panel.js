"use client";

import React, { forwardRef } from 'react';
import classNames from 'classnames';
export const InternalPanel = /*#__PURE__*/forwardRef((props, ref) => {
  const {
    prefixCls,
    className,
    children,
    size,
    style = {}
  } = props;
  const panelClassName = classNames(`${prefixCls}-panel`, {
    [`${prefixCls}-panel-hidden`]: size === 0
  }, className);
  const hasSize = size !== undefined;
  return /*#__PURE__*/React.createElement("div", {
    ref: ref,
    className: panelClassName,
    style: Object.assign(Object.assign({}, style), {
      // Use auto when start from ssr
      flexBasis: hasSize ? size : 'auto',
      flexGrow: hasSize ? 0 : 1
    })
  }, children);
});
if (process.env.NODE_ENV !== 'production') {
  InternalPanel.displayName = 'Panel';
}
const Panel = () => null;
export default Panel;