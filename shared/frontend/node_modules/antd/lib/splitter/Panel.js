"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = exports.InternalPanel = void 0;
var _react = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
const InternalPanel = exports.InternalPanel = /*#__PURE__*/(0, _react.forwardRef)((props, ref) => {
  const {
    prefixCls,
    className,
    children,
    size,
    style = {}
  } = props;
  const panelClassName = (0, _classnames.default)(`${prefixCls}-panel`, {
    [`${prefixCls}-panel-hidden`]: size === 0
  }, className);
  const hasSize = size !== undefined;
  return /*#__PURE__*/_react.default.createElement("div", {
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
var _default = exports.default = Panel;