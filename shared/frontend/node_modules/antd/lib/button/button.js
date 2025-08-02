"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _omit = _interopRequireDefault(require("rc-util/lib/omit"));
var _ref = require("rc-util/lib/ref");
var _warning = require("../_util/warning");
var _wave = _interopRequireDefault(require("../_util/wave"));
var _context = require("../config-provider/context");
var _DisabledContext = _interopRequireDefault(require("../config-provider/DisabledContext"));
var _useSize = _interopRequireDefault(require("../config-provider/hooks/useSize"));
var _Compact = require("../space/Compact");
var _buttonGroup = _interopRequireWildcard(require("./button-group"));
var _buttonHelpers = require("./buttonHelpers");
var _DefaultLoadingIcon = _interopRequireDefault(require("./DefaultLoadingIcon"));
var _IconWrapper = _interopRequireDefault(require("./IconWrapper"));
var _style = _interopRequireDefault(require("./style"));
var _compact = _interopRequireDefault(require("./style/compact"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
function getLoadingConfig(loading) {
  if (typeof loading === 'object' && loading) {
    let delay = loading === null || loading === void 0 ? void 0 : loading.delay;
    delay = !Number.isNaN(delay) && typeof delay === 'number' ? delay : 0;
    return {
      loading: delay <= 0,
      delay
    };
  }
  return {
    loading: !!loading,
    delay: 0
  };
}
const ButtonTypeMap = {
  default: ['default', 'outlined'],
  primary: ['primary', 'solid'],
  dashed: ['default', 'dashed'],
  // `link` is not a real color but we should compatible with it
  link: ['link', 'link'],
  text: ['default', 'text']
};
const InternalCompoundedButton = /*#__PURE__*/_react.default.forwardRef((props, ref) => {
  var _a, _b;
  const {
      loading = false,
      prefixCls: customizePrefixCls,
      color,
      variant,
      type,
      danger = false,
      shape = 'default',
      size: customizeSize,
      styles,
      disabled: customDisabled,
      className,
      rootClassName,
      children,
      icon,
      iconPosition = 'start',
      ghost = false,
      block = false,
      // React does not recognize the `htmlType` prop on a DOM element. Here we pick it out of `rest`.
      htmlType = 'button',
      classNames: customClassNames,
      style: customStyle = {},
      autoInsertSpace,
      autoFocus
    } = props,
    rest = __rest(props, ["loading", "prefixCls", "color", "variant", "type", "danger", "shape", "size", "styles", "disabled", "className", "rootClassName", "children", "icon", "iconPosition", "ghost", "block", "htmlType", "classNames", "style", "autoInsertSpace", "autoFocus"]);
  // https://github.com/ant-design/ant-design/issues/47605
  // Compatible with original `type` behavior
  const mergedType = type || 'default';
  const {
    button
  } = _react.default.useContext(_context.ConfigContext);
  const [mergedColor, mergedVariant] = (0, _react.useMemo)(() => {
    // >>>>> Local
    // Color & Variant
    if (color && variant) {
      return [color, variant];
    }
    // Sugar syntax
    if (type || danger) {
      const colorVariantPair = ButtonTypeMap[mergedType] || [];
      if (danger) {
        return ['danger', colorVariantPair[1]];
      }
      return colorVariantPair;
    }
    // >>> Context fallback
    if ((button === null || button === void 0 ? void 0 : button.color) && (button === null || button === void 0 ? void 0 : button.variant)) {
      return [button.color, button.variant];
    }
    return ['default', 'outlined'];
  }, [type, color, variant, danger, button === null || button === void 0 ? void 0 : button.variant, button === null || button === void 0 ? void 0 : button.color]);
  const isDanger = mergedColor === 'danger';
  const mergedColorText = isDanger ? 'dangerous' : mergedColor;
  const {
    getPrefixCls,
    direction,
    autoInsertSpace: contextAutoInsertSpace,
    className: contextClassName,
    style: contextStyle,
    classNames: contextClassNames,
    styles: contextStyles
  } = (0, _context.useComponentConfig)('button');
  const mergedInsertSpace = (_a = autoInsertSpace !== null && autoInsertSpace !== void 0 ? autoInsertSpace : contextAutoInsertSpace) !== null && _a !== void 0 ? _a : true;
  const prefixCls = getPrefixCls('btn', customizePrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls);
  const disabled = (0, _react.useContext)(_DisabledContext.default);
  const mergedDisabled = customDisabled !== null && customDisabled !== void 0 ? customDisabled : disabled;
  const groupSize = (0, _react.useContext)(_buttonGroup.GroupSizeContext);
  const loadingOrDelay = (0, _react.useMemo)(() => getLoadingConfig(loading), [loading]);
  const [innerLoading, setLoading] = (0, _react.useState)(loadingOrDelay.loading);
  const [hasTwoCNChar, setHasTwoCNChar] = (0, _react.useState)(false);
  const buttonRef = (0, _react.useRef)(null);
  const mergedRef = (0, _ref.useComposeRef)(ref, buttonRef);
  const needInserted = _react.Children.count(children) === 1 && !icon && !(0, _buttonHelpers.isUnBorderedButtonVariant)(mergedVariant);
  // ========================= Mount ==========================
  // Record for mount status.
  // This will help to no to show the animation of loading on the first mount.
  const isMountRef = (0, _react.useRef)(true);
  _react.default.useEffect(() => {
    isMountRef.current = false;
    return () => {
      isMountRef.current = true;
    };
  }, []);
  // ========================= Effect =========================
  // Loading. Should use `useLayoutEffect` to avoid low perf multiple click issue.
  // https://github.com/ant-design/ant-design/issues/51325
  (0, _react.useLayoutEffect)(() => {
    let delayTimer = null;
    if (loadingOrDelay.delay > 0) {
      delayTimer = setTimeout(() => {
        delayTimer = null;
        setLoading(true);
      }, loadingOrDelay.delay);
    } else {
      setLoading(loadingOrDelay.loading);
    }
    function cleanupTimer() {
      if (delayTimer) {
        clearTimeout(delayTimer);
        delayTimer = null;
      }
    }
    return cleanupTimer;
  }, [loadingOrDelay.delay, loadingOrDelay.loading]);
  // Two chinese characters check
  (0, _react.useEffect)(() => {
    // FIXME: for HOC usage like <FormatMessage />
    if (!buttonRef.current || !mergedInsertSpace) {
      return;
    }
    const buttonText = buttonRef.current.textContent || '';
    if (needInserted && (0, _buttonHelpers.isTwoCNChar)(buttonText)) {
      if (!hasTwoCNChar) {
        setHasTwoCNChar(true);
      }
    } else if (hasTwoCNChar) {
      setHasTwoCNChar(false);
    }
  });
  // Auto focus
  (0, _react.useEffect)(() => {
    if (autoFocus && buttonRef.current) {
      buttonRef.current.focus();
    }
  }, []);
  // ========================= Events =========================
  const handleClick = _react.default.useCallback(e => {
    var _a;
    // FIXME: https://github.com/ant-design/ant-design/issues/30207
    if (innerLoading || mergedDisabled) {
      e.preventDefault();
      return;
    }
    (_a = props.onClick) === null || _a === void 0 ? void 0 : _a.call(props, 'href' in props ? e : e);
  }, [props.onClick, innerLoading, mergedDisabled]);
  // ========================== Warn ==========================
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('Button');
    process.env.NODE_ENV !== "production" ? warning(!(typeof icon === 'string' && icon.length > 2), 'breaking', `\`icon\` is using ReactNode instead of string naming in v4. Please check \`${icon}\` at https://ant.design/components/icon`) : void 0;
    process.env.NODE_ENV !== "production" ? warning(!(ghost && (0, _buttonHelpers.isUnBorderedButtonVariant)(mergedVariant)), 'usage', "`link` or `text` button can't be a `ghost` button.") : void 0;
  }
  // ========================== Size ==========================
  const {
    compactSize,
    compactItemClassnames
  } = (0, _Compact.useCompactItemContext)(prefixCls, direction);
  const sizeClassNameMap = {
    large: 'lg',
    small: 'sm',
    middle: undefined
  };
  const sizeFullName = (0, _useSize.default)(ctxSize => {
    var _a, _b;
    return (_b = (_a = customizeSize !== null && customizeSize !== void 0 ? customizeSize : compactSize) !== null && _a !== void 0 ? _a : groupSize) !== null && _b !== void 0 ? _b : ctxSize;
  });
  const sizeCls = sizeFullName ? (_b = sizeClassNameMap[sizeFullName]) !== null && _b !== void 0 ? _b : '' : '';
  const iconType = innerLoading ? 'loading' : icon;
  const linkButtonRestProps = (0, _omit.default)(rest, ['navigate']);
  // ========================= Render =========================
  const classes = (0, _classnames.default)(prefixCls, hashId, cssVarCls, {
    [`${prefixCls}-${shape}`]: shape !== 'default' && shape,
    // Compatible with versions earlier than 5.21.0
    [`${prefixCls}-${mergedType}`]: mergedType,
    [`${prefixCls}-dangerous`]: danger,
    [`${prefixCls}-color-${mergedColorText}`]: mergedColorText,
    [`${prefixCls}-variant-${mergedVariant}`]: mergedVariant,
    [`${prefixCls}-${sizeCls}`]: sizeCls,
    [`${prefixCls}-icon-only`]: !children && children !== 0 && !!iconType,
    [`${prefixCls}-background-ghost`]: ghost && !(0, _buttonHelpers.isUnBorderedButtonVariant)(mergedVariant),
    [`${prefixCls}-loading`]: innerLoading,
    [`${prefixCls}-two-chinese-chars`]: hasTwoCNChar && mergedInsertSpace && !innerLoading,
    [`${prefixCls}-block`]: block,
    [`${prefixCls}-rtl`]: direction === 'rtl',
    [`${prefixCls}-icon-end`]: iconPosition === 'end'
  }, compactItemClassnames, className, rootClassName, contextClassName);
  const fullStyle = Object.assign(Object.assign({}, contextStyle), customStyle);
  const iconClasses = (0, _classnames.default)(customClassNames === null || customClassNames === void 0 ? void 0 : customClassNames.icon, contextClassNames.icon);
  const iconStyle = Object.assign(Object.assign({}, (styles === null || styles === void 0 ? void 0 : styles.icon) || {}), contextStyles.icon || {});
  const iconNode = icon && !innerLoading ? (/*#__PURE__*/_react.default.createElement(_IconWrapper.default, {
    prefixCls: prefixCls,
    className: iconClasses,
    style: iconStyle
  }, icon)) : loading && typeof loading === 'object' && loading.icon ? (/*#__PURE__*/_react.default.createElement(_IconWrapper.default, {
    prefixCls: prefixCls,
    className: iconClasses,
    style: iconStyle
  }, loading.icon)) : (/*#__PURE__*/_react.default.createElement(_DefaultLoadingIcon.default, {
    existIcon: !!icon,
    prefixCls: prefixCls,
    loading: innerLoading,
    mount: isMountRef.current
  }));
  const kids = children || children === 0 ? (0, _buttonHelpers.spaceChildren)(children, needInserted && mergedInsertSpace) : null;
  if (linkButtonRestProps.href !== undefined) {
    return wrapCSSVar(/*#__PURE__*/_react.default.createElement("a", Object.assign({}, linkButtonRestProps, {
      className: (0, _classnames.default)(classes, {
        [`${prefixCls}-disabled`]: mergedDisabled
      }),
      href: mergedDisabled ? undefined : linkButtonRestProps.href,
      style: fullStyle,
      onClick: handleClick,
      ref: mergedRef,
      tabIndex: mergedDisabled ? -1 : 0
    }), iconNode, kids));
  }
  let buttonNode = /*#__PURE__*/_react.default.createElement("button", Object.assign({}, rest, {
    type: htmlType,
    className: classes,
    style: fullStyle,
    onClick: handleClick,
    disabled: mergedDisabled,
    ref: mergedRef
  }), iconNode, kids, compactItemClassnames && /*#__PURE__*/_react.default.createElement(_compact.default, {
    prefixCls: prefixCls
  }));
  if (!(0, _buttonHelpers.isUnBorderedButtonVariant)(mergedVariant)) {
    buttonNode = /*#__PURE__*/_react.default.createElement(_wave.default, {
      component: "Button",
      disabled: innerLoading
    }, buttonNode);
  }
  return wrapCSSVar(buttonNode);
});
const Button = InternalCompoundedButton;
Button.Group = _buttonGroup.default;
Button.__ANT_BUTTON = true;
if (process.env.NODE_ENV !== 'production') {
  Button.displayName = 'Button';
}
var _default = exports.default = Button;