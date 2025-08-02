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
var _classnames = _interopRequireDefault(require("classnames"));
var _rcCascader = _interopRequireDefault(require("rc-cascader"));
var _omit = _interopRequireDefault(require("rc-util/lib/omit"));
var _useZIndex = require("../_util/hooks/useZIndex");
var _motion = require("../_util/motion");
var _PurePanel = _interopRequireDefault(require("../_util/PurePanel"));
var _statusUtils = require("../_util/statusUtils");
var _warning = require("../_util/warning");
var _configProvider = require("../config-provider");
var _context = require("../config-provider/context");
var _defaultRenderEmpty = _interopRequireDefault(require("../config-provider/defaultRenderEmpty"));
var _DisabledContext = _interopRequireDefault(require("../config-provider/DisabledContext"));
var _useCSSVarCls = _interopRequireDefault(require("../config-provider/hooks/useCSSVarCls"));
var _useSize = _interopRequireDefault(require("../config-provider/hooks/useSize"));
var _context2 = require("../form/context");
var _useVariants = _interopRequireDefault(require("../form/hooks/useVariants"));
var _mergedBuiltinPlacements = _interopRequireDefault(require("../select/mergedBuiltinPlacements"));
var _style = _interopRequireDefault(require("../select/style"));
var _useIcons = _interopRequireDefault(require("../select/useIcons"));
var _useShowArrow = _interopRequireDefault(require("../select/useShowArrow"));
var _Compact = require("../space/Compact");
var _useBase = _interopRequireDefault(require("./hooks/useBase"));
var _useCheckable = _interopRequireDefault(require("./hooks/useCheckable"));
var _useColumnIcons = _interopRequireDefault(require("./hooks/useColumnIcons"));
var _Panel = _interopRequireDefault(require("./Panel"));
var _style2 = _interopRequireDefault(require("./style"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const {
  SHOW_CHILD,
  SHOW_PARENT
} = _rcCascader.default;
function highlightKeyword(str, lowerKeyword, prefixCls) {
  const cells = str.toLowerCase().split(lowerKeyword).reduce((list, cur, index) => index === 0 ? [cur] : [].concat((0, _toConsumableArray2.default)(list), [lowerKeyword, cur]), []);
  const fillCells = [];
  let start = 0;
  cells.forEach((cell, index) => {
    const end = start + cell.length;
    let originWorld = str.slice(start, end);
    start = end;
    if (index % 2 === 1) {
      originWorld =
      /*#__PURE__*/
      // eslint-disable-next-line react/no-array-index-key
      React.createElement("span", {
        className: `${prefixCls}-menu-item-keyword`,
        key: `separator-${index}`
      }, originWorld);
    }
    fillCells.push(originWorld);
  });
  return fillCells;
}
const defaultSearchRender = (inputValue, path, prefixCls, fieldNames) => {
  const optionList = [];
  // We do lower here to save perf
  const lower = inputValue.toLowerCase();
  path.forEach((node, index) => {
    if (index !== 0) {
      optionList.push(' / ');
    }
    let label = node[fieldNames.label];
    const type = typeof label;
    if (type === 'string' || type === 'number') {
      label = highlightKeyword(String(label), lower, prefixCls);
    }
    optionList.push(label);
  });
  return optionList;
};
const Cascader = /*#__PURE__*/React.forwardRef((props, ref) => {
  var _a, _b, _c, _d;
  const {
      prefixCls: customizePrefixCls,
      size: customizeSize,
      disabled: customDisabled,
      className,
      rootClassName,
      multiple,
      bordered = true,
      transitionName,
      choiceTransitionName = '',
      popupClassName,
      dropdownClassName,
      expandIcon,
      placement,
      showSearch,
      allowClear = true,
      notFoundContent,
      direction,
      getPopupContainer,
      status: customStatus,
      showArrow,
      builtinPlacements,
      style,
      variant: customVariant,
      dropdownRender,
      onDropdownVisibleChange,
      dropdownMenuColumnStyle,
      popupRender,
      dropdownStyle,
      popupMenuColumnStyle,
      onOpenChange,
      styles,
      classNames
    } = props,
    rest = __rest(props, ["prefixCls", "size", "disabled", "className", "rootClassName", "multiple", "bordered", "transitionName", "choiceTransitionName", "popupClassName", "dropdownClassName", "expandIcon", "placement", "showSearch", "allowClear", "notFoundContent", "direction", "getPopupContainer", "status", "showArrow", "builtinPlacements", "style", "variant", "dropdownRender", "onDropdownVisibleChange", "dropdownMenuColumnStyle", "popupRender", "dropdownStyle", "popupMenuColumnStyle", "onOpenChange", "styles", "classNames"]);
  const restProps = (0, _omit.default)(rest, ['suffixIcon']);
  const {
    getPrefixCls,
    getPopupContainer: getContextPopupContainer,
    className: contextClassName,
    style: contextStyle,
    classNames: contextClassNames,
    styles: contextStyles
  } = (0, _context.useComponentConfig)('cascader');
  const {
    popupOverflow
  } = React.useContext(_configProvider.ConfigContext);
  // =================== Form =====================
  const {
    status: contextStatus,
    hasFeedback,
    isFormItemInput,
    feedbackIcon
  } = React.useContext(_context2.FormItemInputContext);
  const mergedStatus = (0, _statusUtils.getMergedStatus)(contextStatus, customStatus);
  // =================== Warning =====================
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('Cascader');
    // v5 deprecated dropdown api
    const deprecatedProps = {
      dropdownClassName: 'classNames.popup.root',
      dropdownStyle: 'styles.popup.root',
      dropdownRender: 'popupRender',
      dropdownMenuColumnStyle: 'popupMenuColumnStyle',
      onDropdownVisibleChange: 'onOpenChange',
      bordered: 'variant'
    };
    Object.entries(deprecatedProps).forEach(([oldProp, newProp]) => {
      warning.deprecated(!(oldProp in props), oldProp, newProp);
    });
    process.env.NODE_ENV !== "production" ? warning(!('showArrow' in props), 'deprecated', '`showArrow` is deprecated which will be removed in next major version. It will be a default behavior, you can hide it by setting `suffixIcon` to null.') : void 0;
  }
  // ==================== Prefix =====================
  const [prefixCls, cascaderPrefixCls, mergedDirection, renderEmpty] = (0, _useBase.default)(customizePrefixCls, direction);
  const isRtl = mergedDirection === 'rtl';
  const rootPrefixCls = getPrefixCls();
  const rootCls = (0, _useCSSVarCls.default)(prefixCls);
  const [wrapSelectCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls, rootCls);
  const cascaderRootCls = (0, _useCSSVarCls.default)(cascaderPrefixCls);
  const [wrapCascaderCSSVar] = (0, _style2.default)(cascaderPrefixCls, cascaderRootCls);
  const {
    compactSize,
    compactItemClassnames
  } = (0, _Compact.useCompactItemContext)(prefixCls, direction);
  const [variant, enableVariantCls] = (0, _useVariants.default)('cascader', customVariant, bordered);
  // =================== No Found ====================
  const mergedNotFoundContent = notFoundContent || (renderEmpty === null || renderEmpty === void 0 ? void 0 : renderEmpty('Cascader')) || (/*#__PURE__*/React.createElement(_defaultRenderEmpty.default, {
    componentName: "Cascader"
  }));
  // =================== Dropdown ====================
  const mergedPopupClassName = (0, _classnames.default)(((_a = classNames === null || classNames === void 0 ? void 0 : classNames.popup) === null || _a === void 0 ? void 0 : _a.root) || ((_b = contextClassNames.popup) === null || _b === void 0 ? void 0 : _b.root) || popupClassName || dropdownClassName, `${cascaderPrefixCls}-dropdown`, {
    [`${cascaderPrefixCls}-dropdown-rtl`]: mergedDirection === 'rtl'
  }, rootClassName, rootCls, contextClassNames.root, classNames === null || classNames === void 0 ? void 0 : classNames.root, cascaderRootCls, hashId, cssVarCls);
  const mergedPopupRender = popupRender || dropdownRender;
  const mergedPopupMenuColumnStyle = popupMenuColumnStyle || dropdownMenuColumnStyle;
  const mergedOnOpenChange = onOpenChange || onDropdownVisibleChange;
  const mergedPopupStyle = ((_c = styles === null || styles === void 0 ? void 0 : styles.popup) === null || _c === void 0 ? void 0 : _c.root) || ((_d = contextStyles.popup) === null || _d === void 0 ? void 0 : _d.root) || dropdownStyle;
  // ==================== Search =====================
  const mergedShowSearch = React.useMemo(() => {
    if (!showSearch) {
      return showSearch;
    }
    let searchConfig = {
      render: defaultSearchRender
    };
    if (typeof showSearch === 'object') {
      searchConfig = Object.assign(Object.assign({}, searchConfig), showSearch);
    }
    return searchConfig;
  }, [showSearch]);
  // ===================== Size ======================
  const mergedSize = (0, _useSize.default)(ctx => {
    var _a;
    return (_a = customizeSize !== null && customizeSize !== void 0 ? customizeSize : compactSize) !== null && _a !== void 0 ? _a : ctx;
  });
  // ===================== Disabled =====================
  const disabled = React.useContext(_DisabledContext.default);
  const mergedDisabled = customDisabled !== null && customDisabled !== void 0 ? customDisabled : disabled;
  // ===================== Icon ======================
  const [mergedExpandIcon, loadingIcon] = (0, _useColumnIcons.default)(prefixCls, isRtl, expandIcon);
  // =================== Multiple ====================
  const checkable = (0, _useCheckable.default)(cascaderPrefixCls, multiple);
  // ===================== Icons =====================
  const showSuffixIcon = (0, _useShowArrow.default)(props.suffixIcon, showArrow);
  const {
    suffixIcon,
    removeIcon,
    clearIcon
  } = (0, _useIcons.default)(Object.assign(Object.assign({}, props), {
    hasFeedback,
    feedbackIcon,
    showSuffixIcon,
    multiple,
    prefixCls,
    componentName: 'Cascader'
  }));
  // ===================== Placement =====================
  const memoPlacement = React.useMemo(() => {
    if (placement !== undefined) {
      return placement;
    }
    return isRtl ? 'bottomRight' : 'bottomLeft';
  }, [placement, isRtl]);
  const mergedAllowClear = allowClear === true ? {
    clearIcon
  } : allowClear;
  // ============================ zIndex ============================
  const [zIndex] = (0, _useZIndex.useZIndex)('SelectLike', mergedPopupStyle === null || mergedPopupStyle === void 0 ? void 0 : mergedPopupStyle.zIndex);
  // ==================== Render =====================
  const renderNode = /*#__PURE__*/React.createElement(_rcCascader.default, Object.assign({
    prefixCls: prefixCls,
    className: (0, _classnames.default)(!customizePrefixCls && cascaderPrefixCls, {
      [`${prefixCls}-lg`]: mergedSize === 'large',
      [`${prefixCls}-sm`]: mergedSize === 'small',
      [`${prefixCls}-rtl`]: isRtl,
      [`${prefixCls}-${variant}`]: enableVariantCls,
      [`${prefixCls}-in-form-item`]: isFormItemInput
    }, (0, _statusUtils.getStatusClassNames)(prefixCls, mergedStatus, hasFeedback), compactItemClassnames, contextClassName, className, rootClassName, classNames === null || classNames === void 0 ? void 0 : classNames.root, contextClassNames.root, rootCls, cascaderRootCls, hashId, cssVarCls),
    disabled: mergedDisabled,
    style: Object.assign(Object.assign(Object.assign(Object.assign({}, contextStyles.root), styles === null || styles === void 0 ? void 0 : styles.root), contextStyle), style)
  }, restProps, {
    builtinPlacements: (0, _mergedBuiltinPlacements.default)(builtinPlacements, popupOverflow),
    direction: mergedDirection,
    placement: memoPlacement,
    notFoundContent: mergedNotFoundContent,
    allowClear: mergedAllowClear,
    showSearch: mergedShowSearch,
    expandIcon: mergedExpandIcon,
    suffixIcon: suffixIcon,
    removeIcon: removeIcon,
    loadingIcon: loadingIcon,
    checkable: checkable,
    dropdownClassName: mergedPopupClassName,
    dropdownPrefixCls: customizePrefixCls || cascaderPrefixCls,
    dropdownStyle: Object.assign(Object.assign({}, mergedPopupStyle), {
      zIndex
    }),
    dropdownRender: mergedPopupRender,
    dropdownMenuColumnStyle: mergedPopupMenuColumnStyle,
    onOpenChange: mergedOnOpenChange,
    choiceTransitionName: (0, _motion.getTransitionName)(rootPrefixCls, '', choiceTransitionName),
    transitionName: (0, _motion.getTransitionName)(rootPrefixCls, 'slide-up', transitionName),
    getPopupContainer: getPopupContainer || getContextPopupContainer,
    ref: ref
  }));
  return wrapCascaderCSSVar(wrapSelectCSSVar(renderNode));
});
if (process.env.NODE_ENV !== 'production') {
  Cascader.displayName = 'Cascader';
}
// We don't care debug panel
/* istanbul ignore next */
const PurePanel = (0, _PurePanel.default)(Cascader, 'dropdownAlign', props => (0, _omit.default)(props, ['visible']));
Cascader.SHOW_PARENT = SHOW_PARENT;
Cascader.SHOW_CHILD = SHOW_CHILD;
Cascader.Panel = _Panel.default;
Cascader._InternalPanelDoNotUseOrYouWillBeFired = PurePanel;
var _default = exports.default = Cascader;