"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.hasPrefixSuffix = hasPrefixSuffix;
function hasPrefixSuffix(props) {
  return !!(props.prefix || props.suffix || props.allowClear || props.showCount);
}