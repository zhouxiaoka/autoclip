"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
Object.defineProperty(exports, "triggerFocus", {
  enumerable: true,
  get: function () {
    return _commonUtils.triggerFocus;
  }
});
var _react = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcInput = _interopRequireDefault(require("rc-input"));
var _commonUtils = require("rc-input/lib/utils/commonUtils");
var _ref = require("rc-util/lib/ref");
var _ContextIsolator = _interopRequireDefault(require("../_util/ContextIsolator"));
var _getAllowClear = _interopRequireDefault(require("../_util/getAllowClear"));
var _statusUtils = require("../_util/statusUtils");
var _warning = require("../_util/warning");
var _context = require("../config-provider/context");
var _DisabledContext = _interopRequireDefault(require("../config-provider/DisabledContext"));
var _useCSSVarCls = _interopRequireDefault(require("../config-provider/hooks/useCSSVarCls"));
var _useSize = _interopRequireDefault(require("../config-provider/hooks/useSize"));
var _context2 = require("../form/context");
var _useVariants = _interopRequireDefault(require("../form/hooks/useVariants"));
var _Compact = require("../space/Compact");
var _useRemovePasswordTimeout = _interopRequireDefault(require("./hooks/useRemovePasswordTimeout"));
var _style = _interopRequireWildcard(require("./style"));
var _utils = require("./utils");
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const Input = /*#__PURE__*/(0, _react.forwardRef)((props, ref) => {
  const {
      prefixCls: customizePrefixCls,
      bordered = true,
      status: customStatus,
      size: customSize,
      disabled: customDisabled,
      onBlur,
      onFocus,
      suffix,
      allowClear,
      addonAfter,
      addonBefore,
      className,
      style,
      styles,
      rootClassName,
      onChange,
      classNames: classes,
      variant: customVariant
    } = props,
    rest = __rest(props, ["prefixCls", "bordered", "status", "size", "disabled", "onBlur", "onFocus", "suffix", "allowClear", "addonAfter", "addonBefore", "className", "style", "styles", "rootClassName", "onChange", "classNames", "variant"]);
  if (process.env.NODE_ENV !== 'production') {
    const {
      deprecated
    } = (0, _warning.devUseWarning)('Input');
    deprecated(!('bordered' in props), 'bordered', 'variant');
  }
  const {
    getPrefixCls,
    direction,
    allowClear: contextAllowClear,
    autoComplete: contextAutoComplete,
    className: contextClassName,
    style: contextStyle,
    classNames: contextClassNames,
    styles: contextStyles
  } = (0, _context.useComponentConfig)('input');
  const prefixCls = getPrefixCls('input', customizePrefixCls);
  const inputRef = (0, _react.useRef)(null);
  // Style
  const rootCls = (0, _useCSSVarCls.default)(prefixCls);
  const [wrapSharedCSSVar, hashId, cssVarCls] = (0, _style.useSharedStyle)(prefixCls, rootClassName);
  const [wrapCSSVar] = (0, _style.default)(prefixCls, rootCls);
  // ===================== Compact Item =====================
  const {
    compactSize,
    compactItemClassnames
  } = (0, _Compact.useCompactItemContext)(prefixCls, direction);
  // ===================== Size =====================
  const mergedSize = (0, _useSize.default)(ctx => {
    var _a;
    return (_a = customSize !== null && customSize !== void 0 ? customSize : compactSize) !== null && _a !== void 0 ? _a : ctx;
  });
  // ===================== Disabled =====================
  const disabled = _react.default.useContext(_DisabledContext.default);
  const mergedDisabled = customDisabled !== null && customDisabled !== void 0 ? customDisabled : disabled;
  // ===================== Status =====================
  const {
    status: contextStatus,
    hasFeedback,
    feedbackIcon
  } = (0, _react.useContext)(_context2.FormItemInputContext);
  const mergedStatus = (0, _statusUtils.getMergedStatus)(contextStatus, customStatus);
  // ===================== Focus warning =====================
  const inputHasPrefixSuffix = (0, _utils.hasPrefixSuffix)(props) || !!hasFeedback;
  const prevHasPrefixSuffix = (0, _react.useRef)(inputHasPrefixSuffix);
  /* eslint-disable react-hooks/rules-of-hooks */
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('Input');
    (0, _react.useEffect)(() => {
      var _a;
      if (inputHasPrefixSuffix && !prevHasPrefixSuffix.current) {
        process.env.NODE_ENV !== "production" ? warning(document.activeElement === ((_a = inputRef.current) === null || _a === void 0 ? void 0 : _a.input), 'usage', `When Input is focused, dynamic add or remove prefix / suffix will make it lose focus caused by dom structure change. Read more: https://ant.design/components/input/#FAQ`) : void 0;
      }
      prevHasPrefixSuffix.current = inputHasPrefixSuffix;
    }, [inputHasPrefixSuffix]);
  }
  /* eslint-enable */
  // ===================== Remove Password value =====================
  const removePasswordTimeout = (0, _useRemovePasswordTimeout.default)(inputRef, true);
  const handleBlur = e => {
    removePasswordTimeout();
    onBlur === null || onBlur === void 0 ? void 0 : onBlur(e);
  };
  const handleFocus = e => {
    removePasswordTimeout();
    onFocus === null || onFocus === void 0 ? void 0 : onFocus(e);
  };
  const handleChange = e => {
    removePasswordTimeout();
    onChange === null || onChange === void 0 ? void 0 : onChange(e);
  };
  const suffixNode = (hasFeedback || suffix) && (/*#__PURE__*/_react.default.createElement(_react.default.Fragment, null, suffix, hasFeedback && feedbackIcon));
  const mergedAllowClear = (0, _getAllowClear.default)(allowClear !== null && allowClear !== void 0 ? allowClear : contextAllowClear);
  const [variant, enableVariantCls] = (0, _useVariants.default)('input', customVariant, bordered);
  return wrapSharedCSSVar(wrapCSSVar(/*#__PURE__*/_react.default.createElement(_rcInput.default, Object.assign({
    ref: (0, _ref.composeRef)(ref, inputRef),
    prefixCls: prefixCls,
    autoComplete: contextAutoComplete
  }, rest, {
    disabled: mergedDisabled,
    onBlur: handleBlur,
    onFocus: handleFocus,
    style: Object.assign(Object.assign({}, contextStyle), style),
    styles: Object.assign(Object.assign({}, contextStyles), styles),
    suffix: suffixNode,
    allowClear: mergedAllowClear,
    className: (0, _classnames.default)(className, rootClassName, cssVarCls, rootCls, compactItemClassnames, contextClassName),
    onChange: handleChange,
    addonBefore: addonBefore && (/*#__PURE__*/_react.default.createElement(_ContextIsolator.default, {
      form: true,
      space: true
    }, addonBefore)),
    addonAfter: addonAfter && (/*#__PURE__*/_react.default.createElement(_ContextIsolator.default, {
      form: true,
      space: true
    }, addonAfter)),
    classNames: Object.assign(Object.assign(Object.assign({}, classes), contextClassNames), {
      input: (0, _classnames.default)({
        [`${prefixCls}-sm`]: mergedSize === 'small',
        [`${prefixCls}-lg`]: mergedSize === 'large',
        [`${prefixCls}-rtl`]: direction === 'rtl'
      }, classes === null || classes === void 0 ? void 0 : classes.input, contextClassNames.input, hashId),
      variant: (0, _classnames.default)({
        [`${prefixCls}-${variant}`]: enableVariantCls
      }, (0, _statusUtils.getStatusClassNames)(prefixCls, mergedStatus)),
      affixWrapper: (0, _classnames.default)({
        [`${prefixCls}-affix-wrapper-sm`]: mergedSize === 'small',
        [`${prefixCls}-affix-wrapper-lg`]: mergedSize === 'large',
        [`${prefixCls}-affix-wrapper-rtl`]: direction === 'rtl'
      }, hashId),
      wrapper: (0, _classnames.default)({
        [`${prefixCls}-group-rtl`]: direction === 'rtl'
      }, hashId),
      groupWrapper: (0, _classnames.default)({
        [`${prefixCls}-group-wrapper-sm`]: mergedSize === 'small',
        [`${prefixCls}-group-wrapper-lg`]: mergedSize === 'large',
        [`${prefixCls}-group-wrapper-rtl`]: direction === 'rtl',
        [`${prefixCls}-group-wrapper-${variant}`]: enableVariantCls
      }, (0, _statusUtils.getStatusClassNames)(`${prefixCls}-group-wrapper`, mergedStatus, hasFeedback), hashId)
    })
  }))));
});
if (process.env.NODE_ENV !== 'production') {
  Input.displayName = 'Input';
}
var _default = exports.default = Input;