"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireDefault(require("react"));
var _context = require("../form/context");
var _Compact = require("../space/Compact");
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
    result = /*#__PURE__*/_react.default.createElement(_context.NoFormStyle, {
      override: true,
      status: true
    }, result);
  }
  if (space) {
    result = /*#__PURE__*/_react.default.createElement(_Compact.NoCompactStyle, null, result);
  }
  return result;
};
var _default = exports.default = ContextIsolator;