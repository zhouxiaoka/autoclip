"use client";

/* eslint-disable jsx-a11y/heading-has-content */
import * as React from 'react';
import classNames from 'classnames';
const Title = ({
  prefixCls,
  className,
  width,
  style
}) => (
/*#__PURE__*/
// biome-ignore lint/a11y/useHeadingContent: HOC here
React.createElement("h3", {
  className: classNames(prefixCls, className),
  style: Object.assign({
    width
  }, style)
}));
export default Title;