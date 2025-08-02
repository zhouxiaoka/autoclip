"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports._ButtonVariantTypes = exports._ButtonColorTypes = void 0;
exports.convertLegacyProps = convertLegacyProps;
exports.isString = isString;
exports.isTwoCNChar = void 0;
exports.isUnBorderedButtonVariant = isUnBorderedButtonVariant;
exports.spaceChildren = spaceChildren;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var _react = _interopRequireDefault(require("react"));
var _reactNode = require("../_util/reactNode");
var _interface = require("../theme/interface");
const rxTwoCNChar = /^[\u4E00-\u9FA5]{2}$/;
const isTwoCNChar = exports.isTwoCNChar = rxTwoCNChar.test.bind(rxTwoCNChar);
function convertLegacyProps(type) {
  if (type === 'danger') {
    return {
      danger: true
    };
  }
  return {
    type
  };
}
function isString(str) {
  return typeof str === 'string';
}
function isUnBorderedButtonVariant(type) {
  return type === 'text' || type === 'link';
}
function splitCNCharsBySpace(child, needInserted) {
  if (child === null || child === undefined) {
    return;
  }
  const SPACE = needInserted ? ' ' : '';
  if (typeof child !== 'string' && typeof child !== 'number' && isString(child.type) && isTwoCNChar(child.props.children)) {
    return (0, _reactNode.cloneElement)(child, {
      children: child.props.children.split('').join(SPACE)
    });
  }
  if (isString(child)) {
    return isTwoCNChar(child) ? /*#__PURE__*/_react.default.createElement("span", null, child.split('').join(SPACE)) : /*#__PURE__*/_react.default.createElement("span", null, child);
  }
  if ((0, _reactNode.isFragment)(child)) {
    return /*#__PURE__*/_react.default.createElement("span", null, child);
  }
  return child;
}
function spaceChildren(children, needInserted) {
  let isPrevChildPure = false;
  const childList = [];
  _react.default.Children.forEach(children, child => {
    const type = typeof child;
    const isCurrentChildPure = type === 'string' || type === 'number';
    if (isPrevChildPure && isCurrentChildPure) {
      const lastIndex = childList.length - 1;
      const lastChild = childList[lastIndex];
      childList[lastIndex] = `${lastChild}${child}`;
    } else {
      childList.push(child);
    }
    isPrevChildPure = isCurrentChildPure;
  });
  return _react.default.Children.map(childList, child => splitCNCharsBySpace(child, needInserted));
}
const _ButtonTypes = ['default', 'primary', 'dashed', 'link', 'text'];
const _ButtonShapes = ['default', 'circle', 'round'];
const _ButtonHTMLTypes = ['submit', 'button', 'reset'];
const _ButtonVariantTypes = exports._ButtonVariantTypes = ['outlined', 'dashed', 'solid', 'filled', 'text', 'link'];
const _ButtonColorTypes = exports._ButtonColorTypes = ['default', 'primary', 'danger'].concat((0, _toConsumableArray2.default)(_interface.PresetColors));