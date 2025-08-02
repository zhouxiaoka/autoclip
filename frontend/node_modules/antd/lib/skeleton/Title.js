"use strict";
"use client";

/* eslint-disable jsx-a11y/heading-has-content */
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
const Title = ({
  prefixCls,
  className,
  width,
  style
}) => (
/*#__PURE__*/
// biome-ignore lint/a11y/useHeadingContent: HOC here
React.createElement("h3", {
  className: (0, _classnames.default)(prefixCls, className),
  style: Object.assign({
    width
  }, style)
}));
var _default = exports.default = Title;