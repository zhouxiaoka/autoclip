"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireWildcard(require("react"));
var React = _react;
var _classnames = _interopRequireDefault(require("classnames"));
var _rcTextarea = _interopRequireDefault(require("rc-textarea"));
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
var _Input = require("./Input");
var _style = require("./style");
var _textarea = _interopRequireDefault(require("./style/textarea"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const TextArea = /*#__PURE__*/(0, _react.forwardRef)((props, ref) => {
  var _a;
  const {
      prefixCls: customizePrefixCls,
      bordered = true,
      size: customizeSize,
      disabled: customDisabled,
      status: customStatus,
      allowClear,
      classNames: classes,
      rootClassName,
      className,
      style,
      styles,
      variant: customVariant,
      showCount,
      onMouseDown,
      onResize
    } = props,
    rest = __rest(props, ["prefixCls", "bordered", "size", "disabled", "status", "allowClear", "classNames", "rootClassName", "className", "style", "styles", "variant", "showCount", "onMouseDown", "onResize"]);
  if (process.env.NODE_ENV !== 'production') {
    const {
      deprecated
    } = (0, _warning.devUseWarning)('TextArea');
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
  } = (0, _context.useComponentConfig)('textArea');
  // =================== Disabled ===================
  const disabled = React.useContext(_DisabledContext.default);
  const mergedDisabled = customDisabled !== null && customDisabled !== void 0 ? customDisabled : disabled;
  // ==================== Status ====================
  const {
    status: contextStatus,
    hasFeedback,
    feedbackIcon
  } = React.useContext(_context2.FormItemInputContext);
  const mergedStatus = (0, _statusUtils.getMergedStatus)(contextStatus, customStatus);
  // ===================== Ref ======================
  const innerRef = React.useRef(null);
  React.useImperativeHandle(ref, () => {
    var _a;
    return {
      resizableTextArea: (_a = innerRef.current) === null || _a === void 0 ? void 0 : _a.resizableTextArea,
      focus: option => {
        var _a, _b;
        (0, _Input.triggerFocus)((_b = (_a = innerRef.current) === null || _a === void 0 ? void 0 : _a.resizableTextArea) === null || _b === void 0 ? void 0 : _b.textArea, option);
      },
      blur: () => {
        var _a;
        return (_a = innerRef.current) === null || _a === void 0 ? void 0 : _a.blur();
      }
    };
  });
  const prefixCls = getPrefixCls('input', customizePrefixCls);
  // ==================== Style =====================
  const rootCls = (0, _useCSSVarCls.default)(prefixCls);
  const [wrapSharedCSSVar, hashId, cssVarCls] = (0, _style.useSharedStyle)(prefixCls, rootClassName);
  const [wrapCSSVar] = (0, _textarea.default)(prefixCls, rootCls);
  // ================= Compact Item =================
  const {
    compactSize,
    compactItemClassnames
  } = (0, _Compact.useCompactItemContext)(prefixCls, direction);
  // ===================== Size =====================
  const mergedSize = (0, _useSize.default)(ctx => {
    var _a;
    return (_a = customizeSize !== null && customizeSize !== void 0 ? customizeSize : compactSize) !== null && _a !== void 0 ? _a : ctx;
  });
  const [variant, enableVariantCls] = (0, _useVariants.default)('textArea', customVariant, bordered);
  const mergedAllowClear = (0, _getAllowClear.default)(allowClear !== null && allowClear !== void 0 ? allowClear : contextAllowClear);
  // ==================== Resize ====================
  // https://github.com/ant-design/ant-design/issues/51594
  const [isMouseDown, setIsMouseDown] = React.useState(false);
  // When has wrapper, resize will make as dirty for `resize: both` style
  const [resizeDirty, setResizeDirty] = React.useState(false);
  const onInternalMouseDown = e => {
    setIsMouseDown(true);
    onMouseDown === null || onMouseDown === void 0 ? void 0 : onMouseDown(e);
    const onMouseUp = () => {
      setIsMouseDown(false);
      document.removeEventListener('mouseup', onMouseUp);
    };
    document.addEventListener('mouseup', onMouseUp);
  };
  const onInternalResize = size => {
    var _a, _b;
    onResize === null || onResize === void 0 ? void 0 : onResize(size);
    // Change to dirty since this maybe from the `resize: both` style
    if (isMouseDown && typeof getComputedStyle === 'function') {
      const ele = (_b = (_a = innerRef.current) === null || _a === void 0 ? void 0 : _a.nativeElement) === null || _b === void 0 ? void 0 : _b.querySelector('textarea');
      if (ele && getComputedStyle(ele).resize === 'both') {
        setResizeDirty(true);
      }
    }
  };
  // ==================== Render ====================
  return wrapSharedCSSVar(wrapCSSVar(/*#__PURE__*/React.createElement(_rcTextarea.default, Object.assign({
    autoComplete: contextAutoComplete
  }, rest, {
    style: Object.assign(Object.assign({}, contextStyle), style),
    styles: Object.assign(Object.assign({}, contextStyles), styles),
    disabled: mergedDisabled,
    allowClear: mergedAllowClear,
    className: (0, _classnames.default)(cssVarCls, rootCls, className, rootClassName, compactItemClassnames, contextClassName,
    // Only for wrapper
    resizeDirty && `${prefixCls}-textarea-affix-wrapper-resize-dirty`),
    classNames: Object.assign(Object.assign(Object.assign({}, classes), contextClassNames), {
      textarea: (0, _classnames.default)({
        [`${prefixCls}-sm`]: mergedSize === 'small',
        [`${prefixCls}-lg`]: mergedSize === 'large'
      }, hashId, classes === null || classes === void 0 ? void 0 : classes.textarea, contextClassNames.textarea, isMouseDown && `${prefixCls}-mouse-active`),
      variant: (0, _classnames.default)({
        [`${prefixCls}-${variant}`]: enableVariantCls
      }, (0, _statusUtils.getStatusClassNames)(prefixCls, mergedStatus)),
      affixWrapper: (0, _classnames.default)(`${prefixCls}-textarea-affix-wrapper`, {
        [`${prefixCls}-affix-wrapper-rtl`]: direction === 'rtl',
        [`${prefixCls}-affix-wrapper-sm`]: mergedSize === 'small',
        [`${prefixCls}-affix-wrapper-lg`]: mergedSize === 'large',
        [`${prefixCls}-textarea-show-count`]: showCount || ((_a = props.count) === null || _a === void 0 ? void 0 : _a.show)
      }, hashId)
    }),
    prefixCls: prefixCls,
    suffix: hasFeedback && /*#__PURE__*/React.createElement("span", {
      className: `${prefixCls}-textarea-suffix`
    }, feedbackIcon),
    showCount: showCount,
    ref: innerRef,
    onResize: onInternalResize,
    onMouseDown: onInternalMouseDown
  }))));
});
var _default = exports.default = TextArea;