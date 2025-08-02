"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.unstableSetRender = unstableSetRender;
var React = _interopRequireWildcard(require("react"));
var ReactDOM = _interopRequireWildcard(require("react-dom"));
var _render = require("rc-util/lib/React/render");
var _warning = _interopRequireDefault(require("../_util/warning"));
const defaultReactRender = (node, container) => {
  // TODO: Remove in v6
  // Warning for React 19
  if (process.env.NODE_ENV !== 'production') {
    const majorVersion = parseInt(React.version.split('.')[0], 10);
    const fullKeys = Object.keys(ReactDOM);
    process.env.NODE_ENV !== "production" ? (0, _warning.default)(majorVersion < 19 || fullKeys.includes('createRoot'), 'compatible', 'antd v5 support React is 16 ~ 18. see https://u.ant.design/v5-for-19 for compatible.') : void 0;
  }
  (0, _render.render)(node, container);
  return () => {
    return (0, _render.unmount)(container);
  };
};
let unstableRender = defaultReactRender;
/**
 * @deprecated Set React render function for compatible usage.
 * This is internal usage only compatible with React 19.
 * And will be removed in next major version.
 */
function unstableSetRender(render) {
  if (render) {
    unstableRender = render;
  }
  return unstableRender;
}