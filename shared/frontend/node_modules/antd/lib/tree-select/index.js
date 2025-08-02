"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
Object.defineProperty(exports, "TreeNode", {
  enumerable: true,
  get: function () {
    return _rcTreeSelect.TreeNode;
  }
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcTreeSelect = _interopRequireWildcard(require("rc-tree-select"));
var _omit = _interopRequireDefault(require("rc-util/lib/omit"));
var _useZIndex = require("../_util/hooks/useZIndex");
var _motion = require("../_util/motion");
var _PurePanel = _interopRequireDefault(require("../_util/PurePanel"));
var _statusUtils = require("../_util/statusUtils");
var _warning = require("../_util/warning");
var _configProvider = require("../config-provider");
var _defaultRenderEmpty = _interopRequireDefault(require("../config-provider/defaultRenderEmpty"));
var _DisabledContext = _interopRequireDefault(require("../config-provider/DisabledContext"));
var _useCSSVarCls = _interopRequireDefault(require("../config-provider/hooks/useCSSVarCls"));
var _useSize = _interopRequireDefault(require("../config-provider/hooks/useSize"));
var _context = require("../form/context");
var _useVariants = _interopRequireDefault(require("../form/hooks/useVariants"));
var _mergedBuiltinPlacements = _interopRequireDefault(require("../select/mergedBuiltinPlacements"));
var _style = _interopRequireDefault(require("../select/style"));
var _useIcons = _interopRequireDefault(require("../select/useIcons"));
var _useShowArrow = _interopRequireDefault(require("../select/useShowArrow"));
var _Compact = require("../space/Compact");
var _internal = require("../theme/internal");
var _iconUtil = _interopRequireDefault(require("../tree/utils/iconUtil"));
var _style2 = _interopRequireDefault(require("./style"));
var _context2 = require("../config-provider/context");
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const InternalTreeSelect = (props, ref) => {
  var _a, _b, _c, _d, _e;
  const {
      prefixCls: customizePrefixCls,
      size: customizeSize,
      disabled: customDisabled,
      bordered = true,
      style,
      className,
      rootClassName,
      treeCheckable,
      multiple,
      listHeight = 256,
      listItemHeight: customListItemHeight,
      placement,
      notFoundContent,
      switcherIcon,
      treeLine,
      getPopupContainer,
      popupClassName,
      dropdownClassName,
      treeIcon = false,
      transitionName,
      choiceTransitionName = '',
      status: customStatus,
      treeExpandAction,
      builtinPlacements,
      dropdownMatchSelectWidth,
      popupMatchSelectWidth,
      allowClear,
      variant: customVariant,
      dropdownStyle,
      dropdownRender,
      popupRender,
      onDropdownVisibleChange,
      onOpenChange,
      tagRender,
      maxCount,
      showCheckedStrategy,
      treeCheckStrictly,
      styles,
      classNames
    } = props,
    restProps = __rest(props, ["prefixCls", "size", "disabled", "bordered", "style", "className", "rootClassName", "treeCheckable", "multiple", "listHeight", "listItemHeight", "placement", "notFoundContent", "switcherIcon", "treeLine", "getPopupContainer", "popupClassName", "dropdownClassName", "treeIcon", "transitionName", "choiceTransitionName", "status", "treeExpandAction", "builtinPlacements", "dropdownMatchSelectWidth", "popupMatchSelectWidth", "allowClear", "variant", "dropdownStyle", "dropdownRender", "popupRender", "onDropdownVisibleChange", "onOpenChange", "tagRender", "maxCount", "showCheckedStrategy", "treeCheckStrictly", "styles", "classNames"]);
  const {
    getPopupContainer: getContextPopupContainer,
    getPrefixCls,
    renderEmpty,
    direction,
    virtual,
    popupMatchSelectWidth: contextPopupMatchSelectWidth,
    popupOverflow
  } = React.useContext(_configProvider.ConfigContext);
  const {
    styles: contextStyles,
    classNames: contextClassNames
  } = (0, _context2.useComponentConfig)('treeSelect');
  const [, token] = (0, _internal.useToken)();
  const listItemHeight = customListItemHeight !== null && customListItemHeight !== void 0 ? customListItemHeight : (token === null || token === void 0 ? void 0 : token.controlHeightSM) + (token === null || token === void 0 ? void 0 : token.paddingXXS);
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('TreeSelect');
    const deprecatedProps = {
      dropdownMatchSelectWidth: 'popupMatchSelectWidth',
      dropdownStyle: 'styles.popup.root',
      dropdownClassName: 'classNames.popup.root',
      popupClassName: 'classNames.popup.root',
      dropdownRender: 'popupRender',
      onDropdownVisibleChange: 'onOpenChange',
      bordered: 'variant'
    };
    Object.entries(deprecatedProps).forEach(([oldProp, newProp]) => {
      warning.deprecated(!(oldProp in props), oldProp, newProp);
    });
    process.env.NODE_ENV !== "production" ? warning(multiple !== false || !treeCheckable, 'usage', '`multiple` will always be `true` when `treeCheckable` is true') : void 0;
    process.env.NODE_ENV !== "production" ? warning(!('showArrow' in props), 'deprecated', '`showArrow` is deprecated which will be removed in next major version. It will be a default behavior, you can hide it by setting `suffixIcon` to null.') : void 0;
  }
  const rootPrefixCls = getPrefixCls();
  const prefixCls = getPrefixCls('select', customizePrefixCls);
  const treePrefixCls = getPrefixCls('select-tree', customizePrefixCls);
  const treeSelectPrefixCls = getPrefixCls('tree-select', customizePrefixCls);
  const {
    compactSize,
    compactItemClassnames
  } = (0, _Compact.useCompactItemContext)(prefixCls, direction);
  const rootCls = (0, _useCSSVarCls.default)(prefixCls);
  const treeSelectRootCls = (0, _useCSSVarCls.default)(treeSelectPrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls, rootCls);
  const [treeSelectWrapCSSVar] = (0, _style2.default)(treeSelectPrefixCls, treePrefixCls, treeSelectRootCls);
  const [variant, enableVariantCls] = (0, _useVariants.default)('treeSelect', customVariant, bordered);
  const mergedPopupClassName = (0, _classnames.default)(((_a = classNames === null || classNames === void 0 ? void 0 : classNames.popup) === null || _a === void 0 ? void 0 : _a.root) || ((_b = contextClassNames === null || contextClassNames === void 0 ? void 0 : contextClassNames.popup) === null || _b === void 0 ? void 0 : _b.root) || popupClassName || dropdownClassName, `${treeSelectPrefixCls}-dropdown`, {
    [`${treeSelectPrefixCls}-dropdown-rtl`]: direction === 'rtl'
  }, rootClassName, contextClassNames.root, classNames === null || classNames === void 0 ? void 0 : classNames.root, cssVarCls, rootCls, treeSelectRootCls, hashId);
  const mergedPopupStyle = ((_c = styles === null || styles === void 0 ? void 0 : styles.popup) === null || _c === void 0 ? void 0 : _c.root) || ((_d = contextStyles === null || contextStyles === void 0 ? void 0 : contextStyles.popup) === null || _d === void 0 ? void 0 : _d.root) || dropdownStyle;
  const mergedPopupRender = popupRender || dropdownRender;
  const mergedOnOpenChange = onOpenChange || onDropdownVisibleChange;
  const isMultiple = !!(treeCheckable || multiple);
  const mergedMaxCount = React.useMemo(() => {
    if (maxCount && (showCheckedStrategy === 'SHOW_ALL' && !treeCheckStrictly || showCheckedStrategy === 'SHOW_PARENT')) {
      return undefined;
    }
    return maxCount;
  }, [maxCount, showCheckedStrategy, treeCheckStrictly]);
  const showSuffixIcon = (0, _useShowArrow.default)(props.suffixIcon, props.showArrow);
  const mergedPopupMatchSelectWidth = (_e = popupMatchSelectWidth !== null && popupMatchSelectWidth !== void 0 ? popupMatchSelectWidth : dropdownMatchSelectWidth) !== null && _e !== void 0 ? _e : contextPopupMatchSelectWidth;
  // ===================== Form =====================
  const {
    status: contextStatus,
    hasFeedback,
    isFormItemInput,
    feedbackIcon
  } = React.useContext(_context.FormItemInputContext);
  const mergedStatus = (0, _statusUtils.getMergedStatus)(contextStatus, customStatus);
  // ===================== Icons =====================
  const {
    suffixIcon,
    removeIcon,
    clearIcon
  } = (0, _useIcons.default)(Object.assign(Object.assign({}, restProps), {
    multiple: isMultiple,
    showSuffixIcon,
    hasFeedback,
    feedbackIcon,
    prefixCls,
    componentName: 'TreeSelect'
  }));
  const mergedAllowClear = allowClear === true ? {
    clearIcon
  } : allowClear;
  // ===================== Empty =====================
  let mergedNotFound;
  if (notFoundContent !== undefined) {
    mergedNotFound = notFoundContent;
  } else {
    mergedNotFound = (renderEmpty === null || renderEmpty === void 0 ? void 0 : renderEmpty('Select')) || /*#__PURE__*/React.createElement(_defaultRenderEmpty.default, {
      componentName: "Select"
    });
  }
  // ==================== Render =====================
  const selectProps = (0, _omit.default)(restProps, ['suffixIcon', 'removeIcon', 'clearIcon', 'itemIcon', 'switcherIcon', 'style']);
  // ===================== Placement =====================
  const memoizedPlacement = React.useMemo(() => {
    if (placement !== undefined) {
      return placement;
    }
    return direction === 'rtl' ? 'bottomRight' : 'bottomLeft';
  }, [placement, direction]);
  const mergedSize = (0, _useSize.default)(ctx => {
    var _a;
    return (_a = customizeSize !== null && customizeSize !== void 0 ? customizeSize : compactSize) !== null && _a !== void 0 ? _a : ctx;
  });
  // ===================== Disabled =====================
  const disabled = React.useContext(_DisabledContext.default);
  const mergedDisabled = customDisabled !== null && customDisabled !== void 0 ? customDisabled : disabled;
  const mergedClassName = (0, _classnames.default)(!customizePrefixCls && treeSelectPrefixCls, {
    [`${prefixCls}-lg`]: mergedSize === 'large',
    [`${prefixCls}-sm`]: mergedSize === 'small',
    [`${prefixCls}-rtl`]: direction === 'rtl',
    [`${prefixCls}-${variant}`]: enableVariantCls,
    [`${prefixCls}-in-form-item`]: isFormItemInput
  }, (0, _statusUtils.getStatusClassNames)(prefixCls, mergedStatus, hasFeedback), compactItemClassnames, className, rootClassName, contextClassNames.root, classNames === null || classNames === void 0 ? void 0 : classNames.root, cssVarCls, rootCls, treeSelectRootCls, hashId);
  const renderSwitcherIcon = nodeProps => (/*#__PURE__*/React.createElement(_iconUtil.default, {
    prefixCls: treePrefixCls,
    switcherIcon: switcherIcon,
    treeNodeProps: nodeProps,
    showLine: treeLine
  }));
  // ============================ zIndex ============================
  const [zIndex] = (0, _useZIndex.useZIndex)('SelectLike', mergedPopupStyle === null || mergedPopupStyle === void 0 ? void 0 : mergedPopupStyle.zIndex);
  const returnNode = /*#__PURE__*/React.createElement(_rcTreeSelect.default, Object.assign({
    virtual: virtual,
    disabled: mergedDisabled
  }, selectProps, {
    dropdownMatchSelectWidth: mergedPopupMatchSelectWidth,
    builtinPlacements: (0, _mergedBuiltinPlacements.default)(builtinPlacements, popupOverflow),
    ref: ref,
    prefixCls: prefixCls,
    className: mergedClassName,
    style: Object.assign(Object.assign({}, styles === null || styles === void 0 ? void 0 : styles.root), style),
    listHeight: listHeight,
    listItemHeight: listItemHeight,
    treeCheckable: treeCheckable ? /*#__PURE__*/React.createElement("span", {
      className: `${prefixCls}-tree-checkbox-inner`
    }) : treeCheckable,
    treeLine: !!treeLine,
    suffixIcon: suffixIcon,
    multiple: isMultiple,
    placement: memoizedPlacement,
    removeIcon: removeIcon,
    allowClear: mergedAllowClear,
    switcherIcon: renderSwitcherIcon,
    showTreeIcon: treeIcon,
    notFoundContent: mergedNotFound,
    getPopupContainer: getPopupContainer || getContextPopupContainer,
    treeMotion: null,
    dropdownClassName: mergedPopupClassName,
    dropdownStyle: Object.assign(Object.assign({}, mergedPopupStyle), {
      zIndex
    }),
    dropdownRender: mergedPopupRender,
    onDropdownVisibleChange: mergedOnOpenChange,
    choiceTransitionName: (0, _motion.getTransitionName)(rootPrefixCls, '', choiceTransitionName),
    transitionName: (0, _motion.getTransitionName)(rootPrefixCls, 'slide-up', transitionName),
    treeExpandAction: treeExpandAction,
    tagRender: isMultiple ? tagRender : undefined,
    maxCount: mergedMaxCount,
    showCheckedStrategy: showCheckedStrategy,
    treeCheckStrictly: treeCheckStrictly
  }));
  return wrapCSSVar(treeSelectWrapCSSVar(returnNode));
};
const TreeSelectRef = /*#__PURE__*/React.forwardRef(InternalTreeSelect);
const TreeSelect = TreeSelectRef;
// We don't care debug panel
/* istanbul ignore next */
const PurePanel = (0, _PurePanel.default)(TreeSelect, 'dropdownAlign', props => (0, _omit.default)(props, ['visible']));
TreeSelect.TreeNode = _rcTreeSelect.TreeNode;
TreeSelect.SHOW_ALL = _rcTreeSelect.SHOW_ALL;
TreeSelect.SHOW_PARENT = _rcTreeSelect.SHOW_PARENT;
TreeSelect.SHOW_CHILD = _rcTreeSelect.SHOW_CHILD;
TreeSelect._InternalPanelDoNotUseOrYouWillBeFired = PurePanel;
if (process.env.NODE_ENV !== 'production') {
  TreeSelect.displayName = 'TreeSelect';
}
var _default = exports.default = TreeSelect;