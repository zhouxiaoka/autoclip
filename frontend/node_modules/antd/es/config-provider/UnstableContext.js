"use client";

import * as React from 'react';
import * as ReactDOM from 'react-dom';
import { render, unmount } from "rc-util/es/React/render";
import warning from '../_util/warning';
const defaultReactRender = (node, container) => {
  // TODO: Remove in v6
  // Warning for React 19
  if (process.env.NODE_ENV !== 'production') {
    const majorVersion = parseInt(React.version.split('.')[0], 10);
    const fullKeys = Object.keys(ReactDOM);
    process.env.NODE_ENV !== "production" ? warning(majorVersion < 19 || fullKeys.includes('createRoot'), 'compatible', 'antd v5 support React is 16 ~ 18. see https://u.ant.design/v5-for-19 for compatible.') : void 0;
  }
  render(node, container);
  return () => {
    return unmount(container);
  };
};
let unstableRender = defaultReactRender;
/**
 * @deprecated Set React render function for compatible usage.
 * This is internal usage only compatible with React 19.
 * And will be removed in next major version.
 */
export function unstableSetRender(render) {
  if (render) {
    unstableRender = render;
  }
  return unstableRender;
}