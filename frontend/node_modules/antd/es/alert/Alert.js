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
import CheckCircleFilled from "@ant-design/icons/es/icons/CheckCircleFilled";
import CloseCircleFilled from "@ant-design/icons/es/icons/CloseCircleFilled";
import CloseOutlined from "@ant-design/icons/es/icons/CloseOutlined";
import ExclamationCircleFilled from "@ant-design/icons/es/icons/ExclamationCircleFilled";
import InfoCircleFilled from "@ant-design/icons/es/icons/InfoCircleFilled";
import classNames from 'classnames';
import CSSMotion from 'rc-motion';
import pickAttrs from "rc-util/es/pickAttrs";
import { composeRef } from "rc-util/es/ref";
import { replaceElement } from '../_util/reactNode';
import { devUseWarning } from '../_util/warning';
import { useComponentConfig } from '../config-provider/context';
import useStyle from './style';
const iconMapFilled = {
  success: CheckCircleFilled,
  info: InfoCircleFilled,
  error: CloseCircleFilled,
  warning: ExclamationCircleFilled
};
const IconNode = props => {
  const {
    icon,
    prefixCls,
    type
  } = props;
  const iconType = iconMapFilled[type] || null;
  if (icon) {
    return replaceElement(icon, /*#__PURE__*/React.createElement("span", {
      className: `${prefixCls}-icon`
    }, icon), () => ({
      className: classNames(`${prefixCls}-icon`, icon.props.className)
    }));
  }
  return /*#__PURE__*/React.createElement(iconType, {
    className: `${prefixCls}-icon`
  });
};
const CloseIconNode = props => {
  const {
    isClosable,
    prefixCls,
    closeIcon,
    handleClose,
    ariaProps
  } = props;
  const mergedCloseIcon = closeIcon === true || closeIcon === undefined ? /*#__PURE__*/React.createElement(CloseOutlined, null) : closeIcon;
  return isClosable ? (/*#__PURE__*/React.createElement("button", Object.assign({
    type: "button",
    onClick: handleClose,
    className: `${prefixCls}-close-icon`,
    tabIndex: 0
  }, ariaProps), mergedCloseIcon)) : null;
};
const Alert = /*#__PURE__*/React.forwardRef((props, ref) => {
  const {
      description,
      prefixCls: customizePrefixCls,
      message,
      banner,
      className,
      rootClassName,
      style,
      onMouseEnter,
      onMouseLeave,
      onClick,
      afterClose,
      showIcon,
      closable,
      closeText,
      closeIcon,
      action,
      id
    } = props,
    otherProps = __rest(props, ["description", "prefixCls", "message", "banner", "className", "rootClassName", "style", "onMouseEnter", "onMouseLeave", "onClick", "afterClose", "showIcon", "closable", "closeText", "closeIcon", "action", "id"]);
  const [closed, setClosed] = React.useState(false);
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Alert');
    warning.deprecated(!closeText, 'closeText', 'closable.closeIcon');
  }
  const internalRef = React.useRef(null);
  React.useImperativeHandle(ref, () => ({
    nativeElement: internalRef.current
  }));
  const {
    getPrefixCls,
    direction,
    closable: contextClosable,
    closeIcon: contextCloseIcon,
    className: contextClassName,
    style: contextStyle
  } = useComponentConfig('alert');
  const prefixCls = getPrefixCls('alert', customizePrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls);
  const handleClose = e => {
    var _a;
    setClosed(true);
    (_a = props.onClose) === null || _a === void 0 ? void 0 : _a.call(props, e);
  };
  const type = React.useMemo(() => {
    if (props.type !== undefined) {
      return props.type;
    }
    // banner mode defaults to 'warning'
    return banner ? 'warning' : 'info';
  }, [props.type, banner]);
  // closeable when closeText or closeIcon is assigned
  const isClosable = React.useMemo(() => {
    if (typeof closable === 'object' && closable.closeIcon) return true;
    if (closeText) {
      return true;
    }
    if (typeof closable === 'boolean') {
      return closable;
    }
    // should be true when closeIcon is 0 or ''
    if (closeIcon !== false && closeIcon !== null && closeIcon !== undefined) {
      return true;
    }
    return !!contextClosable;
  }, [closeText, closeIcon, closable, contextClosable]);
  // banner mode defaults to Icon
  const isShowIcon = banner && showIcon === undefined ? true : showIcon;
  const alertCls = classNames(prefixCls, `${prefixCls}-${type}`, {
    [`${prefixCls}-with-description`]: !!description,
    [`${prefixCls}-no-icon`]: !isShowIcon,
    [`${prefixCls}-banner`]: !!banner,
    [`${prefixCls}-rtl`]: direction === 'rtl'
  }, contextClassName, className, rootClassName, cssVarCls, hashId);
  const restProps = pickAttrs(otherProps, {
    aria: true,
    data: true
  });
  const mergedCloseIcon = React.useMemo(() => {
    if (typeof closable === 'object' && closable.closeIcon) {
      return closable.closeIcon;
    }
    if (closeText) {
      return closeText;
    }
    if (closeIcon !== undefined) {
      return closeIcon;
    }
    if (typeof contextClosable === 'object' && contextClosable.closeIcon) {
      return contextClosable.closeIcon;
    }
    return contextCloseIcon;
  }, [closeIcon, closable, closeText, contextCloseIcon]);
  const mergedAriaProps = React.useMemo(() => {
    const merged = closable !== null && closable !== void 0 ? closable : contextClosable;
    if (typeof merged === 'object') {
      const {
          closeIcon: _
        } = merged,
        ariaProps = __rest(merged, ["closeIcon"]);
      return ariaProps;
    }
    return {};
  }, [closable, contextClosable]);
  return wrapCSSVar(/*#__PURE__*/React.createElement(CSSMotion, {
    visible: !closed,
    motionName: `${prefixCls}-motion`,
    motionAppear: false,
    motionEnter: false,
    onLeaveStart: node => ({
      maxHeight: node.offsetHeight
    }),
    onLeaveEnd: afterClose
  }, ({
    className: motionClassName,
    style: motionStyle
  }, setRef) => (/*#__PURE__*/React.createElement("div", Object.assign({
    id: id,
    ref: composeRef(internalRef, setRef),
    "data-show": !closed,
    className: classNames(alertCls, motionClassName),
    style: Object.assign(Object.assign(Object.assign({}, contextStyle), style), motionStyle),
    onMouseEnter: onMouseEnter,
    onMouseLeave: onMouseLeave,
    onClick: onClick,
    role: "alert"
  }, restProps), isShowIcon ? (/*#__PURE__*/React.createElement(IconNode, {
    description: description,
    icon: props.icon,
    prefixCls: prefixCls,
    type: type
  })) : null, /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-content`
  }, message ? /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-message`
  }, message) : null, description ? /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-description`
  }, description) : null), action ? /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-action`
  }, action) : null, /*#__PURE__*/React.createElement(CloseIconNode, {
    isClosable: isClosable,
    prefixCls: prefixCls,
    closeIcon: mergedCloseIcon,
    handleClose: handleClose,
    ariaProps: mergedAriaProps
  })))));
});
if (process.env.NODE_ENV !== 'production') {
  Alert.displayName = 'Alert';
}
export default Alert;