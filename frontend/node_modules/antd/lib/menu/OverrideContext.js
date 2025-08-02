"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = exports.OverrideProvider = void 0;
var React = _interopRequireWildcard(require("react"));
var _ref = require("rc-util/lib/ref");
var _ContextIsolator = _interopRequireDefault(require("../_util/ContextIsolator"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const OverrideContext = /*#__PURE__*/React.createContext(null);
/** @internal Only used for Dropdown component. Do not use this in your production. */
const OverrideProvider = exports.OverrideProvider = /*#__PURE__*/React.forwardRef((props, ref) => {
  const {
      children
    } = props,
    restProps = __rest(props, ["children"]);
  const override = React.useContext(OverrideContext);
  const context = React.useMemo(() => Object.assign(Object.assign({}, override), restProps), [override, restProps.prefixCls,
  // restProps.expandIcon, Not mark as deps since this is a ReactNode
  restProps.mode, restProps.selectable, restProps.rootClassName
  // restProps.validator, Not mark as deps since this is a function
  ]);
  const canRef = (0, _ref.supportNodeRef)(children);
  const mergedRef = (0, _ref.useComposeRef)(ref, canRef ? (0, _ref.getNodeRef)(children) : null);
  return /*#__PURE__*/React.createElement(OverrideContext.Provider, {
    value: context
  }, /*#__PURE__*/React.createElement(_ContextIsolator.default, {
    space: true
  }, canRef ? /*#__PURE__*/React.cloneElement(children, {
    ref: mergedRef
  }) : children));
});
/** @internal Only used for Dropdown component. Do not use this in your production. */
var _default = exports.default = OverrideContext;