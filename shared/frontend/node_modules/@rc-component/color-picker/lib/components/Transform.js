"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireWildcard(require("react"));
var Transform = /*#__PURE__*/(0, _react.forwardRef)(function (props, ref) {
  var children = props.children,
    x = props.x,
    y = props.y;
  return /*#__PURE__*/_react.default.createElement("div", {
    ref: ref,
    style: {
      position: 'absolute',
      left: "".concat(x, "%"),
      top: "".concat(y, "%"),
      zIndex: 1,
      transform: 'translate(-50%, -50%)'
    }
  }, children);
});
var _default = exports.default = Transform;