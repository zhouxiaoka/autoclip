"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import React from 'react';
import CloseOutlined from "@ant-design/icons/es/icons/CloseOutlined";
import FileTextOutlined from "@ant-design/icons/es/icons/FileTextOutlined";
import classNames from 'classnames';
import CSSMotion from 'rc-motion';
import useEvent from "rc-util/es/hooks/useEvent";
import useMergedState from "rc-util/es/hooks/useMergedState";
import { useZIndex } from '../_util/hooks/useZIndex';
import { devUseWarning } from '../_util/warning';
import { useComponentConfig } from '../config-provider/context';
import useCSSVarCls from '../config-provider/hooks/useCSSVarCls';
import { FloatButtonGroupProvider } from './context';
import FloatButton, { floatButtonPrefixCls } from './FloatButton';
import useStyle from './style';
const FloatButtonGroup = props => {
  var _a;
  const {
      prefixCls: customizePrefixCls,
      className,
      style,
      shape = 'circle',
      type = 'default',
      placement = 'top',
      icon = /*#__PURE__*/React.createElement(FileTextOutlined, null),
      closeIcon,
      description,
      trigger,
      children,
      onOpenChange,
      open: customOpen,
      onClick: onTriggerButtonClick
    } = props,
    floatButtonProps = __rest(props, ["prefixCls", "className", "style", "shape", "type", "placement", "icon", "closeIcon", "description", "trigger", "children", "onOpenChange", "open", "onClick"]);
  const {
    direction,
    getPrefixCls,
    closeIcon: contextCloseIcon
  } = useComponentConfig('floatButtonGroup');
  const mergedCloseIcon = (_a = closeIcon !== null && closeIcon !== void 0 ? closeIcon : contextCloseIcon) !== null && _a !== void 0 ? _a : /*#__PURE__*/React.createElement(CloseOutlined, null);
  const prefixCls = getPrefixCls(floatButtonPrefixCls, customizePrefixCls);
  const rootCls = useCSSVarCls(prefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls, rootCls);
  const groupPrefixCls = `${prefixCls}-group`;
  const isMenuMode = trigger && ['click', 'hover'].includes(trigger);
  const isValidPlacement = placement && ['top', 'left', 'right', 'bottom'].includes(placement);
  const groupCls = classNames(groupPrefixCls, hashId, cssVarCls, rootCls, className, {
    [`${groupPrefixCls}-rtl`]: direction === 'rtl',
    [`${groupPrefixCls}-${shape}`]: shape,
    [`${groupPrefixCls}-${shape}-shadow`]: !isMenuMode,
    [`${groupPrefixCls}-${placement}`]: isMenuMode && isValidPlacement // 只有菜单模式才支持弹出方向
  });
  // ============================ zIndex ============================
  const [zIndex] = useZIndex('FloatButton', style === null || style === void 0 ? void 0 : style.zIndex);
  const mergedStyle = Object.assign(Object.assign({}, style), {
    zIndex
  });
  const wrapperCls = classNames(hashId, `${groupPrefixCls}-wrap`);
  const [open, setOpen] = useMergedState(false, {
    value: customOpen
  });
  const floatButtonGroupRef = React.useRef(null);
  // ========================== Open ==========================
  const hoverTrigger = trigger === 'hover';
  const clickTrigger = trigger === 'click';
  const triggerOpen = useEvent(nextOpen => {
    if (open !== nextOpen) {
      setOpen(nextOpen);
      onOpenChange === null || onOpenChange === void 0 ? void 0 : onOpenChange(nextOpen);
    }
  });
  // ===================== Trigger: Hover =====================
  const onMouseEnter = () => {
    if (hoverTrigger) {
      triggerOpen(true);
    }
  };
  const onMouseLeave = () => {
    if (hoverTrigger) {
      triggerOpen(false);
    }
  };
  // ===================== Trigger: Click =====================
  const onInternalTriggerButtonClick = e => {
    if (clickTrigger) {
      triggerOpen(!open);
    }
    onTriggerButtonClick === null || onTriggerButtonClick === void 0 ? void 0 : onTriggerButtonClick(e);
  };
  React.useEffect(() => {
    if (clickTrigger) {
      const onDocClick = e => {
        var _a;
        // Skip if click on the group
        if ((_a = floatButtonGroupRef.current) === null || _a === void 0 ? void 0 : _a.contains(e.target)) {
          return;
        }
        triggerOpen(false);
      };
      document.addEventListener('click', onDocClick, {
        capture: true
      });
      return () => document.removeEventListener('click', onDocClick, {
        capture: true
      });
    }
  }, [clickTrigger]);
  // ======================== Warning =========================
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('FloatButton.Group');
    process.env.NODE_ENV !== "production" ? warning(!('open' in props) || !!trigger, 'usage', '`open` need to be used together with `trigger`') : void 0;
  }
  // ========================= Render =========================
  return wrapCSSVar(/*#__PURE__*/React.createElement(FloatButtonGroupProvider, {
    value: shape
  }, /*#__PURE__*/React.createElement("div", {
    ref: floatButtonGroupRef,
    className: groupCls,
    style: mergedStyle,
    // Hover trigger
    onMouseEnter: onMouseEnter,
    onMouseLeave: onMouseLeave
  }, isMenuMode ? (/*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(CSSMotion, {
    visible: open,
    motionName: `${groupPrefixCls}-wrap`
  }, ({
    className: motionClassName
  }) => (/*#__PURE__*/React.createElement("div", {
    className: classNames(motionClassName, wrapperCls)
  }, children))), /*#__PURE__*/React.createElement(FloatButton, Object.assign({
    type: type,
    icon: open ? mergedCloseIcon : icon,
    description: description,
    "aria-label": props['aria-label'],
    className: `${groupPrefixCls}-trigger`,
    onClick: onInternalTriggerButtonClick
  }, floatButtonProps)))) : children)));
};
export default FloatButtonGroup;