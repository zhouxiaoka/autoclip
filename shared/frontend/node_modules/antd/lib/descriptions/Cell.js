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
var _DescriptionsContext = _interopRequireDefault(require("./DescriptionsContext"));
function notEmpty(val) {
  return val !== undefined && val !== null;
}
const Cell = props => {
  const {
    itemPrefixCls,
    component,
    span,
    className,
    style,
    labelStyle,
    contentStyle,
    bordered,
    label,
    content,
    colon,
    type,
    styles
  } = props;
  const Component = component;
  const descContext = React.useContext(_DescriptionsContext.default);
  const {
    classNames: descriptionsClassNames
  } = descContext;
  if (bordered) {
    return /*#__PURE__*/React.createElement(Component, {
      className: (0, _classnames.default)({
        [`${itemPrefixCls}-item-label`]: type === 'label',
        [`${itemPrefixCls}-item-content`]: type === 'content',
        [`${descriptionsClassNames === null || descriptionsClassNames === void 0 ? void 0 : descriptionsClassNames.label}`]: type === 'label',
        [`${descriptionsClassNames === null || descriptionsClassNames === void 0 ? void 0 : descriptionsClassNames.content}`]: type === 'content'
      }, className),
      style: style,
      colSpan: span
    }, notEmpty(label) && /*#__PURE__*/React.createElement("span", {
      style: Object.assign(Object.assign({}, labelStyle), styles === null || styles === void 0 ? void 0 : styles.label)
    }, label), notEmpty(content) && /*#__PURE__*/React.createElement("span", {
      style: Object.assign(Object.assign({}, labelStyle), styles === null || styles === void 0 ? void 0 : styles.content)
    }, content));
  }
  return /*#__PURE__*/React.createElement(Component, {
    className: (0, _classnames.default)(`${itemPrefixCls}-item`, className),
    style: style,
    colSpan: span
  }, /*#__PURE__*/React.createElement("div", {
    className: `${itemPrefixCls}-item-container`
  }, (label || label === 0) && (/*#__PURE__*/React.createElement("span", {
    className: (0, _classnames.default)(`${itemPrefixCls}-item-label`, descriptionsClassNames === null || descriptionsClassNames === void 0 ? void 0 : descriptionsClassNames.label, {
      [`${itemPrefixCls}-item-no-colon`]: !colon
    }),
    style: Object.assign(Object.assign({}, labelStyle), styles === null || styles === void 0 ? void 0 : styles.label)
  }, label)), (content || content === 0) && (/*#__PURE__*/React.createElement("span", {
    className: (0, _classnames.default)(`${itemPrefixCls}-item-content`, descriptionsClassNames === null || descriptionsClassNames === void 0 ? void 0 : descriptionsClassNames.content),
    style: Object.assign(Object.assign({}, contentStyle), styles === null || styles === void 0 ? void 0 : styles.content)
  }, content))));
};
var _default = exports.default = Cell;