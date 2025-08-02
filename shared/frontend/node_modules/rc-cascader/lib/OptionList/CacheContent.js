"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var CacheContent = /*#__PURE__*/React.memo(function (_ref) {
  var children = _ref.children;
  return children;
}, function (_, next) {
  return !next.open;
});
if (process.env.NODE_ENV !== 'production') {
  CacheContent.displayName = 'CacheContent';
}
var _default = exports.default = CacheContent;