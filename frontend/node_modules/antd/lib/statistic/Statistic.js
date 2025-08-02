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
var _pickAttrs = _interopRequireDefault(require("rc-util/lib/pickAttrs"));
var _context = require("../config-provider/context");
var _skeleton = _interopRequireDefault(require("../skeleton"));
var _Number = _interopRequireDefault(require("./Number"));
var _style = _interopRequireDefault(require("./style"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const Statistic = /*#__PURE__*/React.forwardRef((props, ref) => {
  const {
      prefixCls: customizePrefixCls,
      className,
      rootClassName,
      style,
      valueStyle,
      value = 0,
      title,
      valueRender,
      prefix,
      suffix,
      loading = false,
      /* --- FormatConfig starts --- */
      formatter,
      precision,
      decimalSeparator = '.',
      groupSeparator = ',',
      /* --- FormatConfig starts --- */
      onMouseEnter,
      onMouseLeave
    } = props,
    rest = __rest(props, ["prefixCls", "className", "rootClassName", "style", "valueStyle", "value", "title", "valueRender", "prefix", "suffix", "loading", "formatter", "precision", "decimalSeparator", "groupSeparator", "onMouseEnter", "onMouseLeave"]);
  const {
    getPrefixCls,
    direction,
    className: contextClassName,
    style: contextStyle
  } = (0, _context.useComponentConfig)('statistic');
  const prefixCls = getPrefixCls('statistic', customizePrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls);
  const valueNode = /*#__PURE__*/React.createElement(_Number.default, {
    decimalSeparator: decimalSeparator,
    groupSeparator: groupSeparator,
    prefixCls: prefixCls,
    formatter: formatter,
    precision: precision,
    value: value
  });
  const cls = (0, _classnames.default)(prefixCls, {
    [`${prefixCls}-rtl`]: direction === 'rtl'
  }, contextClassName, className, rootClassName, hashId, cssVarCls);
  const internalRef = React.useRef(null);
  React.useImperativeHandle(ref, () => ({
    nativeElement: internalRef.current
  }));
  const restProps = (0, _pickAttrs.default)(rest, {
    aria: true,
    data: true
  });
  return wrapCSSVar(/*#__PURE__*/React.createElement("div", Object.assign({}, restProps, {
    ref: internalRef,
    className: cls,
    style: Object.assign(Object.assign({}, contextStyle), style),
    onMouseEnter: onMouseEnter,
    onMouseLeave: onMouseLeave
  }), title && /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-title`
  }, title), /*#__PURE__*/React.createElement(_skeleton.default, {
    paragraph: false,
    loading: loading,
    className: `${prefixCls}-skeleton`
  }, /*#__PURE__*/React.createElement("div", {
    style: valueStyle,
    className: `${prefixCls}-content`
  }, prefix && /*#__PURE__*/React.createElement("span", {
    className: `${prefixCls}-content-prefix`
  }, prefix), valueRender ? valueRender(valueNode) : valueNode, suffix && /*#__PURE__*/React.createElement("span", {
    className: `${prefixCls}-content-suffix`
  }, suffix)))));
});
if (process.env.NODE_ENV !== 'production') {
  Statistic.displayName = 'Statistic';
}
var _default = exports.default = Statistic;