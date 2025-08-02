"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import * as React from 'react';
import cls from 'classnames';
import RcTreeSelect, { SHOW_ALL, SHOW_CHILD, SHOW_PARENT, TreeNode } from 'rc-tree-select';
import omit from "rc-util/es/omit";
import { useZIndex } from '../_util/hooks/useZIndex';
import { getTransitionName } from '../_util/motion';
import genPurePanel from '../_util/PurePanel';
import { getMergedStatus, getStatusClassNames } from '../_util/statusUtils';
import { devUseWarning } from '../_util/warning';
import { ConfigContext } from '../config-provider';
import DefaultRenderEmpty from '../config-provider/defaultRenderEmpty';
import DisabledContext from '../config-provider/DisabledContext';
import useCSSVarCls from '../config-provider/hooks/useCSSVarCls';
import useSize from '../config-provider/hooks/useSize';
import { FormItemInputContext } from '../form/context';
import useVariant from '../form/hooks/useVariants';
import mergedBuiltinPlacements from '../select/mergedBuiltinPlacements';
import useSelectStyle from '../select/style';
import useIcons from '../select/useIcons';
import useShowArrow from '../select/useShowArrow';
import { useCompactItemContext } from '../space/Compact';
import { useToken } from '../theme/internal';
import SwitcherIconCom from '../tree/utils/iconUtil';
import useStyle from './style';
import { useComponentConfig } from '../config-provider/context';
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
  } = React.useContext(ConfigContext);
  const {
    styles: contextStyles,
    classNames: contextClassNames
  } = useComponentConfig('treeSelect');
  const [, token] = useToken();
  const listItemHeight = customListItemHeight !== null && customListItemHeight !== void 0 ? customListItemHeight : (token === null || token === void 0 ? void 0 : token.controlHeightSM) + (token === null || token === void 0 ? void 0 : token.paddingXXS);
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('TreeSelect');
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
  } = useCompactItemContext(prefixCls, direction);
  const rootCls = useCSSVarCls(prefixCls);
  const treeSelectRootCls = useCSSVarCls(treeSelectPrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useSelectStyle(prefixCls, rootCls);
  const [treeSelectWrapCSSVar] = useStyle(treeSelectPrefixCls, treePrefixCls, treeSelectRootCls);
  const [variant, enableVariantCls] = useVariant('treeSelect', customVariant, bordered);
  const mergedPopupClassName = cls(((_a = classNames === null || classNames === void 0 ? void 0 : classNames.popup) === null || _a === void 0 ? void 0 : _a.root) || ((_b = contextClassNames === null || contextClassNames === void 0 ? void 0 : contextClassNames.popup) === null || _b === void 0 ? void 0 : _b.root) || popupClassName || dropdownClassName, `${treeSelectPrefixCls}-dropdown`, {
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
  const showSuffixIcon = useShowArrow(props.suffixIcon, props.showArrow);
  const mergedPopupMatchSelectWidth = (_e = popupMatchSelectWidth !== null && popupMatchSelectWidth !== void 0 ? popupMatchSelectWidth : dropdownMatchSelectWidth) !== null && _e !== void 0 ? _e : contextPopupMatchSelectWidth;
  // ===================== Form =====================
  const {
    status: contextStatus,
    hasFeedback,
    isFormItemInput,
    feedbackIcon
  } = React.useContext(FormItemInputContext);
  const mergedStatus = getMergedStatus(contextStatus, customStatus);
  // ===================== Icons =====================
  const {
    suffixIcon,
    removeIcon,
    clearIcon
  } = useIcons(Object.assign(Object.assign({}, restProps), {
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
    mergedNotFound = (renderEmpty === null || renderEmpty === void 0 ? void 0 : renderEmpty('Select')) || /*#__PURE__*/React.createElement(DefaultRenderEmpty, {
      componentName: "Select"
    });
  }
  // ==================== Render =====================
  const selectProps = omit(restProps, ['suffixIcon', 'removeIcon', 'clearIcon', 'itemIcon', 'switcherIcon', 'style']);
  // ===================== Placement =====================
  const memoizedPlacement = React.useMemo(() => {
    if (placement !== undefined) {
      return placement;
    }
    return direction === 'rtl' ? 'bottomRight' : 'bottomLeft';
  }, [placement, direction]);
  const mergedSize = useSize(ctx => {
    var _a;
    return (_a = customizeSize !== null && customizeSize !== void 0 ? customizeSize : compactSize) !== null && _a !== void 0 ? _a : ctx;
  });
  // ===================== Disabled =====================
  const disabled = React.useContext(DisabledContext);
  const mergedDisabled = customDisabled !== null && customDisabled !== void 0 ? customDisabled : disabled;
  const mergedClassName = cls(!customizePrefixCls && treeSelectPrefixCls, {
    [`${prefixCls}-lg`]: mergedSize === 'large',
    [`${prefixCls}-sm`]: mergedSize === 'small',
    [`${prefixCls}-rtl`]: direction === 'rtl',
    [`${prefixCls}-${variant}`]: enableVariantCls,
    [`${prefixCls}-in-form-item`]: isFormItemInput
  }, getStatusClassNames(prefixCls, mergedStatus, hasFeedback), compactItemClassnames, className, rootClassName, contextClassNames.root, classNames === null || classNames === void 0 ? void 0 : classNames.root, cssVarCls, rootCls, treeSelectRootCls, hashId);
  const renderSwitcherIcon = nodeProps => (/*#__PURE__*/React.createElement(SwitcherIconCom, {
    prefixCls: treePrefixCls,
    switcherIcon: switcherIcon,
    treeNodeProps: nodeProps,
    showLine: treeLine
  }));
  // ============================ zIndex ============================
  const [zIndex] = useZIndex('SelectLike', mergedPopupStyle === null || mergedPopupStyle === void 0 ? void 0 : mergedPopupStyle.zIndex);
  const returnNode = /*#__PURE__*/React.createElement(RcTreeSelect, Object.assign({
    virtual: virtual,
    disabled: mergedDisabled
  }, selectProps, {
    dropdownMatchSelectWidth: mergedPopupMatchSelectWidth,
    builtinPlacements: mergedBuiltinPlacements(builtinPlacements, popupOverflow),
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
    choiceTransitionName: getTransitionName(rootPrefixCls, '', choiceTransitionName),
    transitionName: getTransitionName(rootPrefixCls, 'slide-up', transitionName),
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
const PurePanel = genPurePanel(TreeSelect, 'dropdownAlign', props => omit(props, ['visible']));
TreeSelect.TreeNode = TreeNode;
TreeSelect.SHOW_ALL = SHOW_ALL;
TreeSelect.SHOW_PARENT = SHOW_PARENT;
TreeSelect.SHOW_CHILD = SHOW_CHILD;
TreeSelect._InternalPanelDoNotUseOrYouWillBeFired = PurePanel;
if (process.env.NODE_ENV !== 'production') {
  TreeSelect.displayName = 'TreeSelect';
}
export { TreeNode };
export default TreeSelect;