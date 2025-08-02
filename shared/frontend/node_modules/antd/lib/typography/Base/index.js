"use strict";
"use client";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var React = _interopRequireWildcard(require("react"));
var _EditOutlined = _interopRequireDefault(require("@ant-design/icons/EditOutlined"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcResizeObserver = _interopRequireDefault(require("rc-resize-observer"));
var _toArray = _interopRequireDefault(require("rc-util/lib/Children/toArray"));
var _useLayoutEffect = _interopRequireDefault(require("rc-util/lib/hooks/useLayoutEffect"));
var _useMergedState = _interopRequireDefault(require("rc-util/lib/hooks/useMergedState"));
var _omit = _interopRequireDefault(require("rc-util/lib/omit"));
var _ref = require("rc-util/lib/ref");
var _styleChecker = require("../../_util/styleChecker");
var _configProvider = require("../../config-provider");
var _useLocale = _interopRequireDefault(require("../../locale/useLocale"));
var _tooltip = _interopRequireDefault(require("../../tooltip"));
var _Editable = _interopRequireDefault(require("../Editable"));
var _useCopyClick = _interopRequireDefault(require("../hooks/useCopyClick"));
var _useMergedConfig = _interopRequireDefault(require("../hooks/useMergedConfig"));
var _usePrevious = _interopRequireDefault(require("../hooks/usePrevious"));
var _useTooltipProps = _interopRequireDefault(require("../hooks/useTooltipProps"));
var _Typography = _interopRequireDefault(require("../Typography"));
var _CopyBtn = _interopRequireDefault(require("./CopyBtn"));
var _Ellipsis = _interopRequireDefault(require("./Ellipsis"));
var _EllipsisTooltip = _interopRequireDefault(require("./EllipsisTooltip"));
var _util = require("./util");
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
function wrapperDecorations({
  mark,
  code,
  underline,
  delete: del,
  strong,
  keyboard,
  italic
}, content) {
  let currentContent = content;
  function wrap(tag, needed) {
    if (!needed) {
      return;
    }
    currentContent = /*#__PURE__*/React.createElement(tag, {}, currentContent);
  }
  wrap('strong', strong);
  wrap('u', underline);
  wrap('del', del);
  wrap('code', code);
  wrap('mark', mark);
  wrap('kbd', keyboard);
  wrap('i', italic);
  return currentContent;
}
const ELLIPSIS_STR = '...';
const DECORATION_PROPS = ['delete', 'mark', 'code', 'underline', 'strong', 'keyboard', 'italic'];
const Base = /*#__PURE__*/React.forwardRef((props, ref) => {
  var _a;
  const {
      prefixCls: customizePrefixCls,
      className,
      style,
      type,
      disabled,
      children,
      ellipsis,
      editable,
      copyable,
      component,
      title
    } = props,
    restProps = __rest(props, ["prefixCls", "className", "style", "type", "disabled", "children", "ellipsis", "editable", "copyable", "component", "title"]);
  const {
    getPrefixCls,
    direction
  } = React.useContext(_configProvider.ConfigContext);
  const [textLocale] = (0, _useLocale.default)('Text');
  const typographyRef = React.useRef(null);
  const editIconRef = React.useRef(null);
  // ============================ MISC ============================
  const prefixCls = getPrefixCls('typography', customizePrefixCls);
  const textProps = (0, _omit.default)(restProps, DECORATION_PROPS);
  // ========================== Editable ==========================
  const [enableEdit, editConfig] = (0, _useMergedConfig.default)(editable);
  const [editing, setEditing] = (0, _useMergedState.default)(false, {
    value: editConfig.editing
  });
  const {
    triggerType = ['icon']
  } = editConfig;
  const triggerEdit = edit => {
    var _a;
    if (edit) {
      (_a = editConfig.onStart) === null || _a === void 0 ? void 0 : _a.call(editConfig);
    }
    setEditing(edit);
  };
  // Focus edit icon when back
  const prevEditing = (0, _usePrevious.default)(editing);
  (0, _useLayoutEffect.default)(() => {
    var _a;
    if (!editing && prevEditing) {
      (_a = editIconRef.current) === null || _a === void 0 ? void 0 : _a.focus();
    }
  }, [editing]);
  const onEditClick = e => {
    e === null || e === void 0 ? void 0 : e.preventDefault();
    triggerEdit(true);
  };
  const onEditChange = value => {
    var _a;
    (_a = editConfig.onChange) === null || _a === void 0 ? void 0 : _a.call(editConfig, value);
    triggerEdit(false);
  };
  const onEditCancel = () => {
    var _a;
    (_a = editConfig.onCancel) === null || _a === void 0 ? void 0 : _a.call(editConfig);
    triggerEdit(false);
  };
  // ========================== Copyable ==========================
  const [enableCopy, copyConfig] = (0, _useMergedConfig.default)(copyable);
  const {
    copied,
    copyLoading,
    onClick: onCopyClick
  } = (0, _useCopyClick.default)({
    copyConfig,
    children
  });
  // ========================== Ellipsis ==========================
  const [isLineClampSupport, setIsLineClampSupport] = React.useState(false);
  const [isTextOverflowSupport, setIsTextOverflowSupport] = React.useState(false);
  const [isJsEllipsis, setIsJsEllipsis] = React.useState(false);
  const [isNativeEllipsis, setIsNativeEllipsis] = React.useState(false);
  const [isNativeVisible, setIsNativeVisible] = React.useState(true);
  const [enableEllipsis, ellipsisConfig] = (0, _useMergedConfig.default)(ellipsis, {
    expandable: false,
    symbol: isExpanded => isExpanded ? textLocale === null || textLocale === void 0 ? void 0 : textLocale.collapse : textLocale === null || textLocale === void 0 ? void 0 : textLocale.expand
  });
  const [expanded, setExpanded] = (0, _useMergedState.default)(ellipsisConfig.defaultExpanded || false, {
    value: ellipsisConfig.expanded
  });
  const mergedEnableEllipsis = enableEllipsis && (!expanded || ellipsisConfig.expandable === 'collapsible');
  // Shared prop to reduce bundle size
  const {
    rows = 1
  } = ellipsisConfig;
  const needMeasureEllipsis = React.useMemo(() =>
  // Disable ellipsis
  mergedEnableEllipsis && (
  // Provide suffix
  ellipsisConfig.suffix !== undefined || ellipsisConfig.onEllipsis ||
  // Can't use css ellipsis since we need to provide the place for button
  ellipsisConfig.expandable || enableEdit || enableCopy), [mergedEnableEllipsis, ellipsisConfig, enableEdit, enableCopy]);
  (0, _useLayoutEffect.default)(() => {
    if (enableEllipsis && !needMeasureEllipsis) {
      setIsLineClampSupport((0, _styleChecker.isStyleSupport)('webkitLineClamp'));
      setIsTextOverflowSupport((0, _styleChecker.isStyleSupport)('textOverflow'));
    }
  }, [needMeasureEllipsis, enableEllipsis]);
  const [cssEllipsis, setCssEllipsis] = React.useState(mergedEnableEllipsis);
  const canUseCssEllipsis = React.useMemo(() => {
    if (needMeasureEllipsis) {
      return false;
    }
    if (rows === 1) {
      return isTextOverflowSupport;
    }
    return isLineClampSupport;
  }, [needMeasureEllipsis, isTextOverflowSupport, isLineClampSupport]);
  // We use effect to change from css ellipsis to js ellipsis.
  // To make SSR still can see the ellipsis.
  (0, _useLayoutEffect.default)(() => {
    setCssEllipsis(canUseCssEllipsis && mergedEnableEllipsis);
  }, [canUseCssEllipsis, mergedEnableEllipsis]);
  const isMergedEllipsis = mergedEnableEllipsis && (cssEllipsis ? isNativeEllipsis : isJsEllipsis);
  const cssTextOverflow = mergedEnableEllipsis && rows === 1 && cssEllipsis;
  const cssLineClamp = mergedEnableEllipsis && rows > 1 && cssEllipsis;
  // >>>>> Expand
  const onExpandClick = (e, info) => {
    var _a;
    setExpanded(info.expanded);
    (_a = ellipsisConfig.onExpand) === null || _a === void 0 ? void 0 : _a.call(ellipsisConfig, e, info);
  };
  const [ellipsisWidth, setEllipsisWidth] = React.useState(0);
  const onResize = ({
    offsetWidth
  }) => {
    setEllipsisWidth(offsetWidth);
  };
  // >>>>> JS Ellipsis
  const onJsEllipsis = jsEllipsis => {
    var _a;
    setIsJsEllipsis(jsEllipsis);
    // Trigger if changed
    if (isJsEllipsis !== jsEllipsis) {
      (_a = ellipsisConfig.onEllipsis) === null || _a === void 0 ? void 0 : _a.call(ellipsisConfig, jsEllipsis);
    }
  };
  // >>>>> Native ellipsis
  React.useEffect(() => {
    const textEle = typographyRef.current;
    if (enableEllipsis && cssEllipsis && textEle) {
      const currentEllipsis = (0, _util.isEleEllipsis)(textEle);
      if (isNativeEllipsis !== currentEllipsis) {
        setIsNativeEllipsis(currentEllipsis);
      }
    }
  }, [enableEllipsis, cssEllipsis, children, cssLineClamp, isNativeVisible, ellipsisWidth]);
  // https://github.com/ant-design/ant-design/issues/36786
  // Use IntersectionObserver to check if element is invisible
  React.useEffect(() => {
    const textEle = typographyRef.current;
    if (typeof IntersectionObserver === 'undefined' || !textEle || !cssEllipsis || !mergedEnableEllipsis) {
      return;
    }
    /* eslint-disable-next-line compat/compat */
    const observer = new IntersectionObserver(() => {
      setIsNativeVisible(!!textEle.offsetParent);
    });
    observer.observe(textEle);
    return () => {
      observer.disconnect();
    };
  }, [cssEllipsis, mergedEnableEllipsis]);
  // ========================== Tooltip ===========================
  const tooltipProps = (0, _useTooltipProps.default)(ellipsisConfig.tooltip, editConfig.text, children);
  const topAriaLabel = React.useMemo(() => {
    if (!enableEllipsis || cssEllipsis) {
      return undefined;
    }
    return [editConfig.text, children, title, tooltipProps.title].find(_util.isValidText);
  }, [enableEllipsis, cssEllipsis, title, tooltipProps.title, isMergedEllipsis]);
  // =========================== Render ===========================
  // >>>>>>>>>>> Editing input
  if (editing) {
    return /*#__PURE__*/React.createElement(_Editable.default, {
      value: (_a = editConfig.text) !== null && _a !== void 0 ? _a : typeof children === 'string' ? children : '',
      onSave: onEditChange,
      onCancel: onEditCancel,
      onEnd: editConfig.onEnd,
      prefixCls: prefixCls,
      className: className,
      style: style,
      direction: direction,
      component: component,
      maxLength: editConfig.maxLength,
      autoSize: editConfig.autoSize,
      enterIcon: editConfig.enterIcon
    });
  }
  // >>>>>>>>>>> Typography
  // Expand
  const renderExpand = () => {
    const {
      expandable,
      symbol
    } = ellipsisConfig;
    return expandable ? (/*#__PURE__*/React.createElement("button", {
      type: "button",
      key: "expand",
      className: `${prefixCls}-${expanded ? 'collapse' : 'expand'}`,
      onClick: e => onExpandClick(e, {
        expanded: !expanded
      }),
      "aria-label": expanded ? textLocale.collapse : textLocale === null || textLocale === void 0 ? void 0 : textLocale.expand
    }, typeof symbol === 'function' ? symbol(expanded) : symbol)) : null;
  };
  // Edit
  const renderEdit = () => {
    if (!enableEdit) {
      return;
    }
    const {
      icon,
      tooltip,
      tabIndex
    } = editConfig;
    const editTitle = (0, _toArray.default)(tooltip)[0] || (textLocale === null || textLocale === void 0 ? void 0 : textLocale.edit);
    const ariaLabel = typeof editTitle === 'string' ? editTitle : '';
    return triggerType.includes('icon') ? (/*#__PURE__*/React.createElement(_tooltip.default, {
      key: "edit",
      title: tooltip === false ? '' : editTitle
    }, /*#__PURE__*/React.createElement("button", {
      type: "button",
      ref: editIconRef,
      className: `${prefixCls}-edit`,
      onClick: onEditClick,
      "aria-label": ariaLabel,
      tabIndex: tabIndex
    }, icon || /*#__PURE__*/React.createElement(_EditOutlined.default, {
      role: "button"
    })))) : null;
  };
  // Copy
  const renderCopy = () => {
    if (!enableCopy) {
      return null;
    }
    return /*#__PURE__*/React.createElement(_CopyBtn.default, Object.assign({
      key: "copy"
    }, copyConfig, {
      prefixCls: prefixCls,
      copied: copied,
      locale: textLocale,
      onCopy: onCopyClick,
      loading: copyLoading,
      iconOnly: children === null || children === undefined
    }));
  };
  const renderOperations = canEllipsis => [canEllipsis && renderExpand(), renderEdit(), renderCopy()];
  const renderEllipsis = canEllipsis => [canEllipsis && !expanded && (/*#__PURE__*/React.createElement("span", {
    "aria-hidden": true,
    key: "ellipsis"
  }, ELLIPSIS_STR)), ellipsisConfig.suffix, renderOperations(canEllipsis)];
  return /*#__PURE__*/React.createElement(_rcResizeObserver.default, {
    onResize: onResize,
    disabled: !mergedEnableEllipsis
  }, resizeRef => (/*#__PURE__*/React.createElement(_EllipsisTooltip.default, {
    tooltipProps: tooltipProps,
    enableEllipsis: mergedEnableEllipsis,
    isEllipsis: isMergedEllipsis
  }, /*#__PURE__*/React.createElement(_Typography.default, Object.assign({
    className: (0, _classnames.default)({
      [`${prefixCls}-${type}`]: type,
      [`${prefixCls}-disabled`]: disabled,
      [`${prefixCls}-ellipsis`]: enableEllipsis,
      [`${prefixCls}-ellipsis-single-line`]: cssTextOverflow,
      [`${prefixCls}-ellipsis-multiple-line`]: cssLineClamp
    }, className),
    prefixCls: customizePrefixCls,
    style: Object.assign(Object.assign({}, style), {
      WebkitLineClamp: cssLineClamp ? rows : undefined
    }),
    component: component,
    ref: (0, _ref.composeRef)(resizeRef, typographyRef, ref),
    direction: direction,
    onClick: triggerType.includes('text') ? onEditClick : undefined,
    "aria-label": topAriaLabel === null || topAriaLabel === void 0 ? void 0 : topAriaLabel.toString(),
    title: title
  }, textProps), /*#__PURE__*/React.createElement(_Ellipsis.default, {
    enableMeasure: mergedEnableEllipsis && !cssEllipsis,
    text: children,
    rows: rows,
    width: ellipsisWidth,
    onEllipsis: onJsEllipsis,
    expanded: expanded,
    miscDeps: [copied, expanded, copyLoading, enableEdit, enableCopy, textLocale].concat((0, _toConsumableArray2.default)(DECORATION_PROPS.map(key => props[key])))
  }, (node, canEllipsis) => wrapperDecorations(props, /*#__PURE__*/React.createElement(React.Fragment, null, node.length > 0 && canEllipsis && !expanded && topAriaLabel ? (/*#__PURE__*/React.createElement("span", {
    key: "show-content",
    "aria-hidden": true
  }, node)) : node, renderEllipsis(canEllipsis))))))));
});
var _default = exports.default = Base;