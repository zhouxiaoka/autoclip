"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import React, { forwardRef, useContext, useEffect, useRef } from 'react';
import classNames from 'classnames';
import RcInput from 'rc-input';
import { triggerFocus } from "rc-input/es/utils/commonUtils";
import { composeRef } from "rc-util/es/ref";
import ContextIsolator from '../_util/ContextIsolator';
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
import useRemovePasswordTimeout from './hooks/useRemovePasswordTimeout';
import useStyle, { useSharedStyle } from './style';
import { hasPrefixSuffix } from './utils';
export { triggerFocus };
const Input = /*#__PURE__*/forwardRef((props, ref) => {
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
    } = devUseWarning('Input');
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
  } = useComponentConfig('input');
  const prefixCls = getPrefixCls('input', customizePrefixCls);
  const inputRef = useRef(null);
  // Style
  const rootCls = useCSSVarCls(prefixCls);
  const [wrapSharedCSSVar, hashId, cssVarCls] = useSharedStyle(prefixCls, rootClassName);
  const [wrapCSSVar] = useStyle(prefixCls, rootCls);
  // ===================== Compact Item =====================
  const {
    compactSize,
    compactItemClassnames
  } = useCompactItemContext(prefixCls, direction);
  // ===================== Size =====================
  const mergedSize = useSize(ctx => {
    var _a;
    return (_a = customSize !== null && customSize !== void 0 ? customSize : compactSize) !== null && _a !== void 0 ? _a : ctx;
  });
  // ===================== Disabled =====================
  const disabled = React.useContext(DisabledContext);
  const mergedDisabled = customDisabled !== null && customDisabled !== void 0 ? customDisabled : disabled;
  // ===================== Status =====================
  const {
    status: contextStatus,
    hasFeedback,
    feedbackIcon
  } = useContext(FormItemInputContext);
  const mergedStatus = getMergedStatus(contextStatus, customStatus);
  // ===================== Focus warning =====================
  const inputHasPrefixSuffix = hasPrefixSuffix(props) || !!hasFeedback;
  const prevHasPrefixSuffix = useRef(inputHasPrefixSuffix);
  /* eslint-disable react-hooks/rules-of-hooks */
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Input');
    useEffect(() => {
      var _a;
      if (inputHasPrefixSuffix && !prevHasPrefixSuffix.current) {
        process.env.NODE_ENV !== "production" ? warning(document.activeElement === ((_a = inputRef.current) === null || _a === void 0 ? void 0 : _a.input), 'usage', `When Input is focused, dynamic add or remove prefix / suffix will make it lose focus caused by dom structure change. Read more: https://ant.design/components/input/#FAQ`) : void 0;
      }
      prevHasPrefixSuffix.current = inputHasPrefixSuffix;
    }, [inputHasPrefixSuffix]);
  }
  /* eslint-enable */
  // ===================== Remove Password value =====================
  const removePasswordTimeout = useRemovePasswordTimeout(inputRef, true);
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
  const suffixNode = (hasFeedback || suffix) && (/*#__PURE__*/React.createElement(React.Fragment, null, suffix, hasFeedback && feedbackIcon));
  const mergedAllowClear = getAllowClear(allowClear !== null && allowClear !== void 0 ? allowClear : contextAllowClear);
  const [variant, enableVariantCls] = useVariant('input', customVariant, bordered);
  return wrapSharedCSSVar(wrapCSSVar(/*#__PURE__*/React.createElement(RcInput, Object.assign({
    ref: composeRef(ref, inputRef),
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
    className: classNames(className, rootClassName, cssVarCls, rootCls, compactItemClassnames, contextClassName),
    onChange: handleChange,
    addonBefore: addonBefore && (/*#__PURE__*/React.createElement(ContextIsolator, {
      form: true,
      space: true
    }, addonBefore)),
    addonAfter: addonAfter && (/*#__PURE__*/React.createElement(ContextIsolator, {
      form: true,
      space: true
    }, addonAfter)),
    classNames: Object.assign(Object.assign(Object.assign({}, classes), contextClassNames), {
      input: classNames({
        [`${prefixCls}-sm`]: mergedSize === 'small',
        [`${prefixCls}-lg`]: mergedSize === 'large',
        [`${prefixCls}-rtl`]: direction === 'rtl'
      }, classes === null || classes === void 0 ? void 0 : classes.input, contextClassNames.input, hashId),
      variant: classNames({
        [`${prefixCls}-${variant}`]: enableVariantCls
      }, getStatusClassNames(prefixCls, mergedStatus)),
      affixWrapper: classNames({
        [`${prefixCls}-affix-wrapper-sm`]: mergedSize === 'small',
        [`${prefixCls}-affix-wrapper-lg`]: mergedSize === 'large',
        [`${prefixCls}-affix-wrapper-rtl`]: direction === 'rtl'
      }, hashId),
      wrapper: classNames({
        [`${prefixCls}-group-rtl`]: direction === 'rtl'
      }, hashId),
      groupWrapper: classNames({
        [`${prefixCls}-group-wrapper-sm`]: mergedSize === 'small',
        [`${prefixCls}-group-wrapper-lg`]: mergedSize === 'large',
        [`${prefixCls}-group-wrapper-rtl`]: direction === 'rtl',
        [`${prefixCls}-group-wrapper-${variant}`]: enableVariantCls
      }, getStatusClassNames(`${prefixCls}-group-wrapper`, mergedStatus, hasFeedback), hashId)
    })
  }))));
});
if (process.env.NODE_ENV !== 'production') {
  Input.displayName = 'Input';
}
export default Input;