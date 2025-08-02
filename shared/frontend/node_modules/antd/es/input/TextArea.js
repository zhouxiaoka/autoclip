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
import { forwardRef } from 'react';
import classNames from 'classnames';
import RcTextArea from 'rc-textarea';
import getAllowClear from '../_util/getAllowClear';
import { getMergedStatus, getStatusClassNames } from '../_util/statusUtils';
import { devUseWarning } from '../_util/warning';
import { useComponentConfig } from '../config-provider/context';
import DisabledContext from '../config-provider/DisabledContext';
import useCSSVarCls from '../config-provider/hooks/useCSSVarCls';
import useSize from '../config-provider/hooks/useSize';
import { FormItemInputContext } from '../form/context';
import useVariant from '../form/hooks/useVariants';
import { useCompactItemContext } from '../space/Compact';
import { triggerFocus } from './Input';
import { useSharedStyle } from './style';
import useStyle from './style/textarea';
const TextArea = /*#__PURE__*/forwardRef((props, ref) => {
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
    } = devUseWarning('TextArea');
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
  } = useComponentConfig('textArea');
  // =================== Disabled ===================
  const disabled = React.useContext(DisabledContext);
  const mergedDisabled = customDisabled !== null && customDisabled !== void 0 ? customDisabled : disabled;
  // ==================== Status ====================
  const {
    status: contextStatus,
    hasFeedback,
    feedbackIcon
  } = React.useContext(FormItemInputContext);
  const mergedStatus = getMergedStatus(contextStatus, customStatus);
  // ===================== Ref ======================
  const innerRef = React.useRef(null);
  React.useImperativeHandle(ref, () => {
    var _a;
    return {
      resizableTextArea: (_a = innerRef.current) === null || _a === void 0 ? void 0 : _a.resizableTextArea,
      focus: option => {
        var _a, _b;
        triggerFocus((_b = (_a = innerRef.current) === null || _a === void 0 ? void 0 : _a.resizableTextArea) === null || _b === void 0 ? void 0 : _b.textArea, option);
      },
      blur: () => {
        var _a;
        return (_a = innerRef.current) === null || _a === void 0 ? void 0 : _a.blur();
      }
    };
  });
  const prefixCls = getPrefixCls('input', customizePrefixCls);
  // ==================== Style =====================
  const rootCls = useCSSVarCls(prefixCls);
  const [wrapSharedCSSVar, hashId, cssVarCls] = useSharedStyle(prefixCls, rootClassName);
  const [wrapCSSVar] = useStyle(prefixCls, rootCls);
  // ================= Compact Item =================
  const {
    compactSize,
    compactItemClassnames
  } = useCompactItemContext(prefixCls, direction);
  // ===================== Size =====================
  const mergedSize = useSize(ctx => {
    var _a;
    return (_a = customizeSize !== null && customizeSize !== void 0 ? customizeSize : compactSize) !== null && _a !== void 0 ? _a : ctx;
  });
  const [variant, enableVariantCls] = useVariant('textArea', customVariant, bordered);
  const mergedAllowClear = getAllowClear(allowClear !== null && allowClear !== void 0 ? allowClear : contextAllowClear);
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
  return wrapSharedCSSVar(wrapCSSVar(/*#__PURE__*/React.createElement(RcTextArea, Object.assign({
    autoComplete: contextAutoComplete
  }, rest, {
    style: Object.assign(Object.assign({}, contextStyle), style),
    styles: Object.assign(Object.assign({}, contextStyles), styles),
    disabled: mergedDisabled,
    allowClear: mergedAllowClear,
    className: classNames(cssVarCls, rootCls, className, rootClassName, compactItemClassnames, contextClassName,
    // Only for wrapper
    resizeDirty && `${prefixCls}-textarea-affix-wrapper-resize-dirty`),
    classNames: Object.assign(Object.assign(Object.assign({}, classes), contextClassNames), {
      textarea: classNames({
        [`${prefixCls}-sm`]: mergedSize === 'small',
        [`${prefixCls}-lg`]: mergedSize === 'large'
      }, hashId, classes === null || classes === void 0 ? void 0 : classes.textarea, contextClassNames.textarea, isMouseDown && `${prefixCls}-mouse-active`),
      variant: classNames({
        [`${prefixCls}-${variant}`]: enableVariantCls
      }, getStatusClassNames(prefixCls, mergedStatus)),
      affixWrapper: classNames(`${prefixCls}-textarea-affix-wrapper`, {
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
export default TextArea;