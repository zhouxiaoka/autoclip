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
import classNames from 'classnames';
import RcCheckbox from 'rc-checkbox';
import { composeRef } from "rc-util/es/ref";
import { devUseWarning } from '../_util/warning';
import Wave from '../_util/wave';
import { TARGET_CLS } from '../_util/wave/interface';
import useBubbleLock from '../checkbox/useBubbleLock';
import { ConfigContext } from '../config-provider';
import DisabledContext from '../config-provider/DisabledContext';
import useCSSVarCls from '../config-provider/hooks/useCSSVarCls';
import { FormItemInputContext } from '../form/context';
import RadioGroupContext, { RadioOptionTypeContext } from './context';
import useStyle from './style';
const InternalRadio = (props, ref) => {
  var _a, _b;
  const groupContext = React.useContext(RadioGroupContext);
  const radioOptionTypeContext = React.useContext(RadioOptionTypeContext);
  const {
    getPrefixCls,
    direction,
    radio
  } = React.useContext(ConfigContext);
  const innerRef = React.useRef(null);
  const mergedRef = composeRef(ref, innerRef);
  const {
    isFormItemInput
  } = React.useContext(FormItemInputContext);
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Radio');
    process.env.NODE_ENV !== "production" ? warning(!('optionType' in props), 'usage', '`optionType` is only support in Radio.Group.') : void 0;
  }
  const onChange = e => {
    var _a, _b;
    (_a = props.onChange) === null || _a === void 0 ? void 0 : _a.call(props, e);
    (_b = groupContext === null || groupContext === void 0 ? void 0 : groupContext.onChange) === null || _b === void 0 ? void 0 : _b.call(groupContext, e);
  };
  const {
      prefixCls: customizePrefixCls,
      className,
      rootClassName,
      children,
      style,
      title
    } = props,
    restProps = __rest(props, ["prefixCls", "className", "rootClassName", "children", "style", "title"]);
  const radioPrefixCls = getPrefixCls('radio', customizePrefixCls);
  const isButtonType = ((groupContext === null || groupContext === void 0 ? void 0 : groupContext.optionType) || radioOptionTypeContext) === 'button';
  const prefixCls = isButtonType ? `${radioPrefixCls}-button` : radioPrefixCls;
  // Style
  const rootCls = useCSSVarCls(radioPrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(radioPrefixCls, rootCls);
  const radioProps = Object.assign({}, restProps);
  // ===================== Disabled =====================
  const disabled = React.useContext(DisabledContext);
  if (groupContext) {
    radioProps.name = groupContext.name;
    radioProps.onChange = onChange;
    radioProps.checked = props.value === groupContext.value;
    radioProps.disabled = (_a = radioProps.disabled) !== null && _a !== void 0 ? _a : groupContext.disabled;
  }
  radioProps.disabled = (_b = radioProps.disabled) !== null && _b !== void 0 ? _b : disabled;
  const wrapperClassString = classNames(`${prefixCls}-wrapper`, {
    [`${prefixCls}-wrapper-checked`]: radioProps.checked,
    [`${prefixCls}-wrapper-disabled`]: radioProps.disabled,
    [`${prefixCls}-wrapper-rtl`]: direction === 'rtl',
    [`${prefixCls}-wrapper-in-form-item`]: isFormItemInput,
    [`${prefixCls}-wrapper-block`]: !!(groupContext === null || groupContext === void 0 ? void 0 : groupContext.block)
  }, radio === null || radio === void 0 ? void 0 : radio.className, className, rootClassName, hashId, cssVarCls, rootCls);
  // ============================ Event Lock ============================
  const [onLabelClick, onInputClick] = useBubbleLock(radioProps.onClick);
  // ============================== Render ==============================
  return wrapCSSVar(/*#__PURE__*/React.createElement(Wave, {
    component: "Radio",
    disabled: radioProps.disabled
  }, /*#__PURE__*/React.createElement("label", {
    className: wrapperClassString,
    style: Object.assign(Object.assign({}, radio === null || radio === void 0 ? void 0 : radio.style), style),
    onMouseEnter: props.onMouseEnter,
    onMouseLeave: props.onMouseLeave,
    title: title,
    onClick: onLabelClick
  }, /*#__PURE__*/React.createElement(RcCheckbox, Object.assign({}, radioProps, {
    className: classNames(radioProps.className, {
      [TARGET_CLS]: !isButtonType
    }),
    type: "radio",
    prefixCls: prefixCls,
    ref: mergedRef,
    onClick: onInputClick
  })), children !== undefined ? /*#__PURE__*/React.createElement("span", {
    className: `${prefixCls}-label`
  }, children) : null)));
};
const Radio = /*#__PURE__*/React.forwardRef(InternalRadio);
if (process.env.NODE_ENV !== 'production') {
  Radio.displayName = 'Radio';
}
export default Radio;