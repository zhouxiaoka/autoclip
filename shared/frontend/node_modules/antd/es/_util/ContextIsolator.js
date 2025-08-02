"use client";

import React from 'react';
import { NoFormStyle } from '../form/context';
import { NoCompactStyle } from '../space/Compact';
const ContextIsolator = props => {
  const {
    space,
    form,
    children
  } = props;
  if (children === undefined || children === null) {
    return null;
  }
  let result = children;
  if (form) {
    result = /*#__PURE__*/React.createElement(NoFormStyle, {
      override: true,
      status: true
    }, result);
  }
  if (space) {
    result = /*#__PURE__*/React.createElement(NoCompactStyle, null, result);
  }
  return result;
};
export default ContextIsolator;