"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
var _typeof = require("@babel/runtime/helpers/typeof");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _objectWithoutProperties2 = _interopRequireDefault(require("@babel/runtime/helpers/objectWithoutProperties"));
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _Item = _interopRequireDefault(require("./Item"));
var _context = require("./context");
var _excluded = ["component"],
  _excluded2 = ["className"],
  _excluded3 = ["className"];
function _getRequireWildcardCache(e) { if ("function" != typeof WeakMap) return null; var r = new WeakMap(), t = new WeakMap(); return (_getRequireWildcardCache = function _getRequireWildcardCache(e) { return e ? t : r; })(e); }
function _interopRequireWildcard(e, r) { if (!r && e && e.__esModule) return e; if (null === e || "object" != _typeof(e) && "function" != typeof e) return { default: e }; var t = _getRequireWildcardCache(r); if (t && t.has(e)) return t.get(e); var n = { __proto__: null }, a = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var u in e) if ("default" !== u && Object.prototype.hasOwnProperty.call(e, u)) { var i = a ? Object.getOwnPropertyDescriptor(e, u) : null; i && (i.get || i.set) ? Object.defineProperty(n, u, i) : n[u] = e[u]; } return n.default = e, t && t.set(e, n), n; }
var InternalRawItem = function InternalRawItem(props, ref) {
  var context = React.useContext(_context.OverflowContext);

  // Render directly when context not provided
  if (!context) {
    var _props$component = props.component,
      Component = _props$component === void 0 ? 'div' : _props$component,
      _restProps = (0, _objectWithoutProperties2.default)(props, _excluded);
    return /*#__PURE__*/React.createElement(Component, (0, _extends2.default)({}, _restProps, {
      ref: ref
    }));
  }
  var contextClassName = context.className,
    restContext = (0, _objectWithoutProperties2.default)(context, _excluded2);
  var className = props.className,
    restProps = (0, _objectWithoutProperties2.default)(props, _excluded3);

  // Do not pass context to sub item to avoid multiple measure
  return /*#__PURE__*/React.createElement(_context.OverflowContext.Provider, {
    value: null
  }, /*#__PURE__*/React.createElement(_Item.default, (0, _extends2.default)({
    ref: ref,
    className: (0, _classnames.default)(contextClassName, className)
  }, restContext, restProps)));
};
var RawItem = /*#__PURE__*/React.forwardRef(InternalRawItem);
RawItem.displayName = 'RawItem';
var _default = exports.default = RawItem;