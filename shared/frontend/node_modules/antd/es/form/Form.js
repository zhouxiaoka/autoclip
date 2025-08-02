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
import FieldForm, { List, useWatch } from 'rc-field-form';
import { useComponentConfig } from '../config-provider/context';
import DisabledContext, { DisabledContextProvider } from '../config-provider/DisabledContext';
import useCSSVarCls from '../config-provider/hooks/useCSSVarCls';
import useSize from '../config-provider/hooks/useSize';
import SizeContext from '../config-provider/SizeContext';
import { FormContext, FormProvider, VariantContext } from './context';
import useForm from './hooks/useForm';
import useFormWarning from './hooks/useFormWarning';
import useStyle from './style';
import ValidateMessagesContext from './validateMessagesContext';
const InternalForm = (props, ref) => {
  const contextDisabled = React.useContext(DisabledContext);
  const {
    getPrefixCls,
    direction,
    requiredMark: contextRequiredMark,
    colon: contextColon,
    scrollToFirstError: contextScrollToFirstError,
    className: contextClassName,
    style: contextStyle
  } = useComponentConfig('form');
  const {
      prefixCls: customizePrefixCls,
      className,
      rootClassName,
      size,
      disabled = contextDisabled,
      form,
      colon,
      labelAlign,
      labelWrap,
      labelCol,
      wrapperCol,
      hideRequiredMark,
      layout = 'horizontal',
      scrollToFirstError,
      requiredMark,
      onFinishFailed,
      name,
      style,
      feedbackIcons,
      variant
    } = props,
    restFormProps = __rest(props, ["prefixCls", "className", "rootClassName", "size", "disabled", "form", "colon", "labelAlign", "labelWrap", "labelCol", "wrapperCol", "hideRequiredMark", "layout", "scrollToFirstError", "requiredMark", "onFinishFailed", "name", "style", "feedbackIcons", "variant"]);
  const mergedSize = useSize(size);
  const contextValidateMessages = React.useContext(ValidateMessagesContext);
  if (process.env.NODE_ENV !== 'production') {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useFormWarning(props);
  }
  const mergedRequiredMark = React.useMemo(() => {
    if (requiredMark !== undefined) {
      return requiredMark;
    }
    if (hideRequiredMark) {
      return false;
    }
    if (contextRequiredMark !== undefined) {
      return contextRequiredMark;
    }
    return true;
  }, [hideRequiredMark, requiredMark, contextRequiredMark]);
  const mergedColon = colon !== null && colon !== void 0 ? colon : contextColon;
  const prefixCls = getPrefixCls('form', customizePrefixCls);
  // Style
  const rootCls = useCSSVarCls(prefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls, rootCls);
  const formClassName = classNames(prefixCls, `${prefixCls}-${layout}`, {
    [`${prefixCls}-hide-required-mark`]: mergedRequiredMark === false,
    // todo: remove in next major version
    [`${prefixCls}-rtl`]: direction === 'rtl',
    [`${prefixCls}-${mergedSize}`]: mergedSize
  }, cssVarCls, rootCls, hashId, contextClassName, className, rootClassName);
  const [wrapForm] = useForm(form);
  const {
    __INTERNAL__
  } = wrapForm;
  __INTERNAL__.name = name;
  const formContextValue = React.useMemo(() => ({
    name,
    labelAlign,
    labelCol,
    labelWrap,
    wrapperCol,
    vertical: layout === 'vertical',
    colon: mergedColon,
    requiredMark: mergedRequiredMark,
    itemRef: __INTERNAL__.itemRef,
    form: wrapForm,
    feedbackIcons
  }), [name, labelAlign, labelCol, wrapperCol, layout, mergedColon, mergedRequiredMark, wrapForm, feedbackIcons]);
  const nativeElementRef = React.useRef(null);
  React.useImperativeHandle(ref, () => {
    var _a;
    return Object.assign(Object.assign({}, wrapForm), {
      nativeElement: (_a = nativeElementRef.current) === null || _a === void 0 ? void 0 : _a.nativeElement
    });
  });
  const scrollToField = (options, fieldName) => {
    if (options) {
      let defaultScrollToFirstError = {
        block: 'nearest'
      };
      if (typeof options === 'object') {
        defaultScrollToFirstError = Object.assign(Object.assign({}, defaultScrollToFirstError), options);
      }
      wrapForm.scrollToField(fieldName, defaultScrollToFirstError);
    }
  };
  const onInternalFinishFailed = errorInfo => {
    onFinishFailed === null || onFinishFailed === void 0 ? void 0 : onFinishFailed(errorInfo);
    if (errorInfo.errorFields.length) {
      const fieldName = errorInfo.errorFields[0].name;
      if (scrollToFirstError !== undefined) {
        scrollToField(scrollToFirstError, fieldName);
        return;
      }
      if (contextScrollToFirstError !== undefined) {
        scrollToField(contextScrollToFirstError, fieldName);
      }
    }
  };
  return wrapCSSVar(/*#__PURE__*/React.createElement(VariantContext.Provider, {
    value: variant
  }, /*#__PURE__*/React.createElement(DisabledContextProvider, {
    disabled: disabled
  }, /*#__PURE__*/React.createElement(SizeContext.Provider, {
    value: mergedSize
  }, /*#__PURE__*/React.createElement(FormProvider, {
    // This is not list in API, we pass with spread
    validateMessages: contextValidateMessages
  }, /*#__PURE__*/React.createElement(FormContext.Provider, {
    value: formContextValue
  }, /*#__PURE__*/React.createElement(FieldForm, Object.assign({
    id: name
  }, restFormProps, {
    name: name,
    onFinishFailed: onInternalFinishFailed,
    form: wrapForm,
    ref: nativeElementRef,
    style: Object.assign(Object.assign({}, contextStyle), style),
    className: formClassName
  }))))))));
};
const Form = /*#__PURE__*/React.forwardRef(InternalForm);
if (process.env.NODE_ENV !== 'production') {
  Form.displayName = 'Form';
}
export { List, useForm, useWatch };
export default Form;