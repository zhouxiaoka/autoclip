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
import ExclamationCircleFilled from "@ant-design/icons/es/icons/ExclamationCircleFilled";
import classNames from 'classnames';
import useMergedState from "rc-util/es/hooks/useMergedState";
import omit from "rc-util/es/omit";
import { useComponentConfig } from '../config-provider/context';
import Popover from '../popover';
import PurePanel, { Overlay } from './PurePanel';
import useStyle from './style';
const InternalPopconfirm = /*#__PURE__*/React.forwardRef((props, ref) => {
  var _a, _b;
  const {
      prefixCls: customizePrefixCls,
      placement = 'top',
      trigger = 'click',
      okType = 'primary',
      icon = /*#__PURE__*/React.createElement(ExclamationCircleFilled, null),
      children,
      overlayClassName,
      onOpenChange,
      onVisibleChange,
      overlayStyle,
      styles,
      classNames: popconfirmClassNames
    } = props,
    restProps = __rest(props, ["prefixCls", "placement", "trigger", "okType", "icon", "children", "overlayClassName", "onOpenChange", "onVisibleChange", "overlayStyle", "styles", "classNames"]);
  const {
    getPrefixCls,
    className: contextClassName,
    style: contextStyle,
    classNames: contextClassNames,
    styles: contextStyles
  } = useComponentConfig('popconfirm');
  const [open, setOpen] = useMergedState(false, {
    value: (_a = props.open) !== null && _a !== void 0 ? _a : props.visible,
    defaultValue: (_b = props.defaultOpen) !== null && _b !== void 0 ? _b : props.defaultVisible
  });
  const settingOpen = (value, e) => {
    setOpen(value, true);
    onVisibleChange === null || onVisibleChange === void 0 ? void 0 : onVisibleChange(value);
    onOpenChange === null || onOpenChange === void 0 ? void 0 : onOpenChange(value, e);
  };
  const close = e => {
    settingOpen(false, e);
  };
  const onConfirm = e => {
    var _a;
    return (_a = props.onConfirm) === null || _a === void 0 ? void 0 : _a.call(this, e);
  };
  const onCancel = e => {
    var _a;
    settingOpen(false, e);
    (_a = props.onCancel) === null || _a === void 0 ? void 0 : _a.call(this, e);
  };
  const onInternalOpenChange = (value, e) => {
    const {
      disabled = false
    } = props;
    if (disabled) {
      return;
    }
    settingOpen(value, e);
  };
  const prefixCls = getPrefixCls('popconfirm', customizePrefixCls);
  const rootClassNames = classNames(prefixCls, contextClassName, overlayClassName, contextClassNames.root, popconfirmClassNames === null || popconfirmClassNames === void 0 ? void 0 : popconfirmClassNames.root);
  const bodyClassNames = classNames(contextClassNames.body, popconfirmClassNames === null || popconfirmClassNames === void 0 ? void 0 : popconfirmClassNames.body);
  const [wrapCSSVar] = useStyle(prefixCls);
  return wrapCSSVar(/*#__PURE__*/React.createElement(Popover, Object.assign({}, omit(restProps, ['title']), {
    trigger: trigger,
    placement: placement,
    onOpenChange: onInternalOpenChange,
    open: open,
    ref: ref,
    classNames: {
      root: rootClassNames,
      body: bodyClassNames
    },
    styles: {
      root: Object.assign(Object.assign(Object.assign(Object.assign({}, contextStyles.root), contextStyle), overlayStyle), styles === null || styles === void 0 ? void 0 : styles.root),
      body: Object.assign(Object.assign({}, contextStyles.body), styles === null || styles === void 0 ? void 0 : styles.body)
    },
    content: /*#__PURE__*/React.createElement(Overlay, Object.assign({
      okType: okType,
      icon: icon
    }, props, {
      prefixCls: prefixCls,
      close: close,
      onConfirm: onConfirm,
      onCancel: onCancel
    })),
    "data-popover-inject": true
  }), children));
});
const Popconfirm = InternalPopconfirm;
// We don't care debug panel
/* istanbul ignore next */
Popconfirm._InternalPanelDoNotUseOrYouWillBeFired = PurePanel;
if (process.env.NODE_ENV !== 'production') {
  Popconfirm.displayName = 'Popconfirm';
}
export default Popconfirm;