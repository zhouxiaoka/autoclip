"use client";

import * as React from 'react';
import { Provider as MotionProvider } from 'rc-motion';
import { useToken } from '../theme/internal';
const MotionCacheContext = /*#__PURE__*/React.createContext(true);
if (process.env.NODE_ENV !== 'production') {
  MotionCacheContext.displayName = 'MotionCacheContext';
}
export default function MotionWrapper(props) {
  const parentMotion = React.useContext(MotionCacheContext);
  const {
    children
  } = props;
  const [, token] = useToken();
  const {
    motion
  } = token;
  const needWrapMotionProviderRef = React.useRef(false);
  needWrapMotionProviderRef.current || (needWrapMotionProviderRef.current = parentMotion !== motion);
  if (needWrapMotionProviderRef.current) {
    return /*#__PURE__*/React.createElement(MotionCacheContext.Provider, {
      value: motion
    }, /*#__PURE__*/React.createElement(MotionProvider, {
      motion: motion
    }, children));
  }
  return children;
}