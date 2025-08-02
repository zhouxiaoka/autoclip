"use client";

import _toConsumableArray from "@babel/runtime/helpers/esm/toConsumableArray";
var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import * as React from 'react';
import EditOutlined from "@ant-design/icons/es/icons/EditOutlined";
import classNames from 'classnames';
import ResizeObserver from 'rc-resize-observer';
import toArray from "rc-util/es/Children/toArray";
import useLayoutEffect from "rc-util/es/hooks/useLayoutEffect";
import useMergedState from "rc-util/es/hooks/useMergedState";
import omit from "rc-util/es/omit";
import { composeRef } from "rc-util/es/ref";
import { isStyleSupport } from '../../_util/styleChecker';
import { ConfigContext } from '../../config-provider';
import useLocale from '../../locale/useLocale';
import Tooltip from '../../tooltip';
import Editable from '../Editable';
import useCopyClick from '../hooks/useCopyClick';
import useMergedConfig from '../hooks/useMergedConfig';
import usePrevious from '../hooks/usePrevious';
import useTooltipProps from '../hooks/useTooltipProps';
import Typography from '../Typography';
import CopyBtn from './CopyBtn';
import Ellipsis from './Ellipsis';
import EllipsisTooltip from './EllipsisTooltip';
import { isEleEllipsis, isValidText } from './util';
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
  } = React.useContext(ConfigContext);
  const [textLocale] = useLocale('Text');
  const typographyRef = React.useRef(null);
  const editIconRef = React.useRef(null);
  // ============================ MISC ============================
  const prefixCls = getPrefixCls('typography', customizePrefixCls);
  const textProps = omit(restProps, DECORATION_PROPS);
  // ========================== Editable ==========================
  const [enableEdit, editConfig] = useMergedConfig(editable);
  const [editing, setEditing] = useMergedState(false, {
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
  const prevEditing = usePrevious(editing);
  useLayoutEffect(() => {
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
  const [enableCopy, copyConfig] = useMergedConfig(copyable);
  const {
    copied,
    copyLoading,
    onClick: onCopyClick
  } = useCopyClick({
    copyConfig,
    children
  });
  // ========================== Ellipsis ==========================
  const [isLineClampSupport, setIsLineClampSupport] = React.useState(false);
  const [isTextOverflowSupport, setIsTextOverflowSupport] = React.useState(false);
  const [isJsEllipsis, setIsJsEllipsis] = React.useState(false);
  const [isNativeEllipsis, setIsNativeEllipsis] = React.useState(false);
  const [isNativeVisible, setIsNativeVisible] = React.useState(true);
  const [enableEllipsis, ellipsisConfig] = useMergedConfig(ellipsis, {
    expandable: false,
    symbol: isExpanded => isExpanded ? textLocale === null || textLocale === void 0 ? void 0 : textLocale.collapse : textLocale === null || textLocale === void 0 ? void 0 : textLocale.expand
  });
  const [expanded, setExpanded] = useMergedState(ellipsisConfig.defaultExpanded || false, {
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
  useLayoutEffect(() => {
    if (enableEllipsis && !needMeasureEllipsis) {
      setIsLineClampSupport(isStyleSupport('webkitLineClamp'));
      setIsTextOverflowSupport(isStyleSupport('textOverflow'));
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
  useLayoutEffect(() => {
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
      const currentEllipsis = isEleEllipsis(textEle);
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
  const tooltipProps = useTooltipProps(ellipsisConfig.tooltip, editConfig.text, children);
  const topAriaLabel = React.useMemo(() => {
    if (!enableEllipsis || cssEllipsis) {
      return undefined;
    }
    return [editConfig.text, children, title, tooltipProps.title].find(isValidText);
  }, [enableEllipsis, cssEllipsis, title, tooltipProps.title, isMergedEllipsis]);
  // =========================== Render ===========================
  // >>>>>>>>>>> Editing input
  if (editing) {
    return /*#__PURE__*/React.createElement(Editable, {
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
    const editTitle = toArray(tooltip)[0] || (textLocale === null || textLocale === void 0 ? void 0 : textLocale.edit);
    const ariaLabel = typeof editTitle === 'string' ? editTitle : '';
    return triggerType.includes('icon') ? (/*#__PURE__*/React.createElement(Tooltip, {
      key: "edit",
      title: tooltip === false ? '' : editTitle
    }, /*#__PURE__*/React.createElement("button", {
      type: "button",
      ref: editIconRef,
      className: `${prefixCls}-edit`,
      onClick: onEditClick,
      "aria-label": ariaLabel,
      tabIndex: tabIndex
    }, icon || /*#__PURE__*/React.createElement(EditOutlined, {
      role: "button"
    })))) : null;
  };
  // Copy
  const renderCopy = () => {
    if (!enableCopy) {
      return null;
    }
    return /*#__PURE__*/React.createElement(CopyBtn, Object.assign({
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
  return /*#__PURE__*/React.createElement(ResizeObserver, {
    onResize: onResize,
    disabled: !mergedEnableEllipsis
  }, resizeRef => (/*#__PURE__*/React.createElement(EllipsisTooltip, {
    tooltipProps: tooltipProps,
    enableEllipsis: mergedEnableEllipsis,
    isEllipsis: isMergedEllipsis
  }, /*#__PURE__*/React.createElement(Typography, Object.assign({
    className: classNames({
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
    ref: composeRef(resizeRef, typographyRef, ref),
    direction: direction,
    onClick: triggerType.includes('text') ? onEditClick : undefined,
    "aria-label": topAriaLabel === null || topAriaLabel === void 0 ? void 0 : topAriaLabel.toString(),
    title: title
  }, textProps), /*#__PURE__*/React.createElement(Ellipsis, {
    enableMeasure: mergedEnableEllipsis && !cssEllipsis,
    text: children,
    rows: rows,
    width: ellipsisWidth,
    onEllipsis: onJsEllipsis,
    expanded: expanded,
    miscDeps: [copied, expanded, copyLoading, enableEdit, enableCopy, textLocale].concat(_toConsumableArray(DECORATION_PROPS.map(key => props[key])))
  }, (node, canEllipsis) => wrapperDecorations(props, /*#__PURE__*/React.createElement(React.Fragment, null, node.length > 0 && canEllipsis && !expanded && topAriaLabel ? (/*#__PURE__*/React.createElement("span", {
    key: "show-content",
    "aria-hidden": true
  }, node)) : node, renderEllipsis(canEllipsis))))))));
});
export default Base;