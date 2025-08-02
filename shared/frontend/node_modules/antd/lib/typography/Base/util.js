"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.getNode = getNode;
exports.isEleEllipsis = isEleEllipsis;
exports.isValidText = void 0;
exports.toList = toList;
function toList(val) {
  if (val === false) {
    return [false, false];
  }
  return Array.isArray(val) ? val : [val];
}
function getNode(dom, defaultNode, needDom) {
  if (dom === true || dom === undefined) {
    return defaultNode;
  }
  return dom || needDom && defaultNode;
}
/**
 * Check for element is native ellipsis
 * ref:
 * - https://github.com/ant-design/ant-design/issues/50143
 * - https://github.com/ant-design/ant-design/issues/50414
 */
function isEleEllipsis(ele) {
  // Create a new div to get the size
  const childDiv = document.createElement('em');
  ele.appendChild(childDiv);
  // For test case
  if (process.env.NODE_ENV !== 'production') {
    childDiv.className = 'ant-typography-css-ellipsis-content-measure';
  }
  const rect = ele.getBoundingClientRect();
  const childRect = childDiv.getBoundingClientRect();
  // Reset
  ele.removeChild(childDiv);
  // Range checker
  return (
    // Horizontal out of range
    rect.left > childRect.left || childRect.right > rect.right ||
    // Vertical out of range
    rect.top > childRect.top || childRect.bottom > rect.bottom
  );
}
const isValidText = val => ['string', 'number'].includes(typeof val);
exports.isValidText = isValidText;