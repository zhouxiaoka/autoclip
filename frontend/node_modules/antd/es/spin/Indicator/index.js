"use client";

import * as React from 'react';
import classNames from 'classnames';
import { cloneElement } from '../../_util/reactNode';
import Looper from './Looper';
export default function Indicator(props) {
  const {
    prefixCls,
    indicator,
    percent
  } = props;
  const dotClassName = `${prefixCls}-dot`;
  if (indicator && /*#__PURE__*/React.isValidElement(indicator)) {
    return cloneElement(indicator, {
      className: classNames(indicator.props.className, dotClassName),
      percent
    });
  }
  return /*#__PURE__*/React.createElement(Looper, {
    prefixCls: prefixCls,
    percent: percent
  });
}