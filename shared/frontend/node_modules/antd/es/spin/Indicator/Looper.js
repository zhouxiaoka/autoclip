"use client";

import * as React from 'react';
import classNames from 'classnames';
import Progress from './Progress';
export default function Looper(props) {
  const {
    prefixCls,
    percent = 0
  } = props;
  const dotClassName = `${prefixCls}-dot`;
  const holderClassName = `${dotClassName}-holder`;
  const hideClassName = `${holderClassName}-hidden`;
  // ===================== Render =====================
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
    className: classNames(holderClassName, percent > 0 && hideClassName)
  }, /*#__PURE__*/React.createElement("span", {
    className: classNames(dotClassName, `${prefixCls}-dot-spin`)
  }, [1, 2, 3, 4].map(i => (/*#__PURE__*/React.createElement("i", {
    className: `${prefixCls}-dot-item`,
    key: i
  }))))), /*#__PURE__*/React.createElement(Progress, {
    prefixCls: prefixCls,
    percent: percent
  }));
}