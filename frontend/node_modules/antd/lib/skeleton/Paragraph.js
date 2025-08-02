"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
const getWidth = (index, props) => {
  const {
    width,
    rows = 2
  } = props;
  if (Array.isArray(width)) {
    return width[index];
  }
  // last paragraph
  if (rows - 1 === index) {
    return width;
  }
  return undefined;
};
const Paragraph = props => {
  const {
    prefixCls,
    className,
    style,
    rows = 0
  } = props;
  const rowList = Array.from({
    length: rows
  }).map((_, index) => (
  /*#__PURE__*/
  // eslint-disable-next-line react/no-array-index-key
  React.createElement("li", {
    key: index,
    style: {
      width: getWidth(index, props)
    }
  })));
  return /*#__PURE__*/React.createElement("ul", {
    className: (0, _classnames.default)(prefixCls, className),
    style: style
  }, rowList);
};
var _default = exports.default = Paragraph;