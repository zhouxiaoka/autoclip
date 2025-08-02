"use strict";
"use client";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = MotionWrapper;
var React = _interopRequireWildcard(require("react"));
var _rcMotion = require("rc-motion");
var _internal = require("../theme/internal");
const MotionCacheContext = /*#__PURE__*/React.createContext(true);
if (process.env.NODE_ENV !== 'production') {
  MotionCacheContext.displayName = 'MotionCacheContext';
}
function MotionWrapper(props) {
  const parentMotion = React.useContext(MotionCacheContext);
  const {
    children
  } = props;
  const [, token] = (0, _internal.useToken)();
  const {
    motion
  } = token;
  const needWrapMotionProviderRef = React.useRef(false);
  needWrapMotionProviderRef.current || (needWrapMotionProviderRef.current = parentMotion !== motion);
  if (needWrapMotionProviderRef.current) {
    return /*#__PURE__*/React.createElement(MotionCacheContext.Provider, {
      value: motion
    }, /*#__PURE__*/React.createElement(_rcMotion.Provider, {
      motion: motion
    }, children));
  }
  return children;
}