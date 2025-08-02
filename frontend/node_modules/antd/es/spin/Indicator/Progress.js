"use client";

import * as React from 'react';
import classNames from 'classnames';
import useLayoutEffect from "rc-util/es/hooks/useLayoutEffect";
const viewSize = 100;
const borderWidth = viewSize / 5;
const radius = viewSize / 2 - borderWidth / 2;
const circumference = radius * 2 * Math.PI;
const position = 50;
const CustomCircle = props => {
  const {
    dotClassName,
    style,
    hasCircleCls
  } = props;
  return /*#__PURE__*/React.createElement("circle", {
    className: classNames(`${dotClassName}-circle`, {
      [`${dotClassName}-circle-bg`]: hasCircleCls
    }),
    r: radius,
    cx: position,
    cy: position,
    strokeWidth: borderWidth,
    style: style
  });
};
const Progress = ({
  percent,
  prefixCls
}) => {
  const dotClassName = `${prefixCls}-dot`;
  const holderClassName = `${dotClassName}-holder`;
  const hideClassName = `${holderClassName}-hidden`;
  const [render, setRender] = React.useState(false);
  // ==================== Visible =====================
  useLayoutEffect(() => {
    if (percent !== 0) {
      setRender(true);
    }
  }, [percent !== 0]);
  // ==================== Progress ====================
  const safePtg = Math.max(Math.min(percent, 100), 0);
  // ===================== Render =====================
  if (!render) {
    return null;
  }
  const circleStyle = {
    strokeDashoffset: `${circumference / 4}`,
    strokeDasharray: `${circumference * safePtg / 100} ${circumference * (100 - safePtg) / 100}`
  };
  return /*#__PURE__*/React.createElement("span", {
    className: classNames(holderClassName, `${dotClassName}-progress`, safePtg <= 0 && hideClassName)
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${viewSize} ${viewSize}`,
    // biome-ignore lint/a11y/noNoninteractiveElementToInteractiveRole: progressbar could be readonly
    role: "progressbar",
    "aria-valuemin": 0,
    "aria-valuemax": 100,
    "aria-valuenow": safePtg
  }, /*#__PURE__*/React.createElement(CustomCircle, {
    dotClassName: dotClassName,
    hasCircleCls: true
  }), /*#__PURE__*/React.createElement(CustomCircle, {
    dotClassName: dotClassName,
    style: circleStyle
  })));
};
export default Progress;