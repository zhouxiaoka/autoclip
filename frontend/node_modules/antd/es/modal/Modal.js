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
import CloseOutlined from "@ant-design/icons/es/icons/CloseOutlined";
import classNames from 'classnames';
import Dialog from 'rc-dialog';
import ContextIsolator from '../_util/ContextIsolator';
import useClosable, { pickClosable } from '../_util/hooks/useClosable';
import { useZIndex } from '../_util/hooks/useZIndex';
import { getTransitionName } from '../_util/motion';
import { canUseDocElement } from '../_util/styleChecker';
import { devUseWarning } from '../_util/warning';
import zIndexContext from '../_util/zindexContext';
import { ConfigContext } from '../config-provider';
import useCSSVarCls from '../config-provider/hooks/useCSSVarCls';
import Skeleton from '../skeleton';
import { usePanelRef } from '../watermark/context';
import { Footer, renderCloseIcon } from './shared';
import useStyle from './style';
let mousePosition;
// ref: https://github.com/ant-design/ant-design/issues/15795
const getClickPosition = e => {
  mousePosition = {
    x: e.pageX,
    y: e.pageY
  };
  // 100ms 内发生过点击事件，则从点击位置动画展示
  // 否则直接 zoom 展示
  // 这样可以兼容非点击方式展开
  setTimeout(() => {
    mousePosition = null;
  }, 100);
};
// 只有点击事件支持从鼠标位置动画展开
if (canUseDocElement()) {
  document.documentElement.addEventListener('click', getClickPosition, true);
}
const Modal = props => {
  const {
      prefixCls: customizePrefixCls,
      className,
      rootClassName,
      open,
      wrapClassName,
      centered,
      getContainer,
      focusTriggerAfterClose = true,
      style,
      // Deprecated
      visible,
      width = 520,
      footer,
      classNames: modalClassNames,
      styles: modalStyles,
      children,
      loading,
      confirmLoading,
      zIndex: customizeZIndex,
      mousePosition: customizeMousePosition,
      onOk,
      onCancel,
      destroyOnHidden,
      destroyOnClose
    } = props,
    restProps = __rest(props, ["prefixCls", "className", "rootClassName", "open", "wrapClassName", "centered", "getContainer", "focusTriggerAfterClose", "style", "visible", "width", "footer", "classNames", "styles", "children", "loading", "confirmLoading", "zIndex", "mousePosition", "onOk", "onCancel", "destroyOnHidden", "destroyOnClose"]);
  const {
    getPopupContainer: getContextPopupContainer,
    getPrefixCls,
    direction,
    modal: modalContext
  } = React.useContext(ConfigContext);
  const handleCancel = e => {
    if (confirmLoading) {
      return;
    }
    onCancel === null || onCancel === void 0 ? void 0 : onCancel(e);
  };
  const handleOk = e => {
    onOk === null || onOk === void 0 ? void 0 : onOk(e);
  };
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Modal');
    [['visible', 'open'], ['bodyStyle', 'styles.body'], ['maskStyle', 'styles.mask'], ['destroyOnClose', 'destroyOnHidden']].forEach(([deprecatedName, newName]) => {
      warning.deprecated(!(deprecatedName in props), deprecatedName, newName);
    });
  }
  const prefixCls = getPrefixCls('modal', customizePrefixCls);
  const rootPrefixCls = getPrefixCls();
  // Style
  const rootCls = useCSSVarCls(prefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls, rootCls);
  const wrapClassNameExtended = classNames(wrapClassName, {
    [`${prefixCls}-centered`]: centered !== null && centered !== void 0 ? centered : modalContext === null || modalContext === void 0 ? void 0 : modalContext.centered,
    [`${prefixCls}-wrap-rtl`]: direction === 'rtl'
  });
  const dialogFooter = footer !== null && !loading ? (/*#__PURE__*/React.createElement(Footer, Object.assign({}, props, {
    onOk: handleOk,
    onCancel: handleCancel
  }))) : null;
  const [mergedClosable, mergedCloseIcon, closeBtnIsDisabled, ariaProps] = useClosable(pickClosable(props), pickClosable(modalContext), {
    closable: true,
    closeIcon: /*#__PURE__*/React.createElement(CloseOutlined, {
      className: `${prefixCls}-close-icon`
    }),
    closeIconRender: icon => renderCloseIcon(prefixCls, icon)
  });
  // ============================ Refs ============================
  // Select `ant-modal-content` by `panelRef`
  const panelRef = usePanelRef(`.${prefixCls}-content`);
  // ============================ zIndex ============================
  const [zIndex, contextZIndex] = useZIndex('Modal', customizeZIndex);
  // =========================== Width ============================
  const [numWidth, responsiveWidth] = React.useMemo(() => {
    if (width && typeof width === 'object') {
      return [undefined, width];
    }
    return [width, undefined];
  }, [width]);
  const responsiveWidthVars = React.useMemo(() => {
    const vars = {};
    if (responsiveWidth) {
      Object.keys(responsiveWidth).forEach(breakpoint => {
        const breakpointWidth = responsiveWidth[breakpoint];
        if (breakpointWidth !== undefined) {
          vars[`--${prefixCls}-${breakpoint}-width`] = typeof breakpointWidth === 'number' ? `${breakpointWidth}px` : breakpointWidth;
        }
      });
    }
    return vars;
  }, [responsiveWidth]);
  // =========================== Render ===========================
  return wrapCSSVar(/*#__PURE__*/React.createElement(ContextIsolator, {
    form: true,
    space: true
  }, /*#__PURE__*/React.createElement(zIndexContext.Provider, {
    value: contextZIndex
  }, /*#__PURE__*/React.createElement(Dialog, Object.assign({
    width: numWidth
  }, restProps, {
    zIndex: zIndex,
    getContainer: getContainer === undefined ? getContextPopupContainer : getContainer,
    prefixCls: prefixCls,
    rootClassName: classNames(hashId, rootClassName, cssVarCls, rootCls),
    footer: dialogFooter,
    visible: open !== null && open !== void 0 ? open : visible,
    mousePosition: customizeMousePosition !== null && customizeMousePosition !== void 0 ? customizeMousePosition : mousePosition,
    onClose: handleCancel,
    closable: mergedClosable ? Object.assign({
      disabled: closeBtnIsDisabled,
      closeIcon: mergedCloseIcon
    }, ariaProps) : mergedClosable,
    closeIcon: mergedCloseIcon,
    focusTriggerAfterClose: focusTriggerAfterClose,
    transitionName: getTransitionName(rootPrefixCls, 'zoom', props.transitionName),
    maskTransitionName: getTransitionName(rootPrefixCls, 'fade', props.maskTransitionName),
    className: classNames(hashId, className, modalContext === null || modalContext === void 0 ? void 0 : modalContext.className),
    style: Object.assign(Object.assign(Object.assign({}, modalContext === null || modalContext === void 0 ? void 0 : modalContext.style), style), responsiveWidthVars),
    classNames: Object.assign(Object.assign(Object.assign({}, modalContext === null || modalContext === void 0 ? void 0 : modalContext.classNames), modalClassNames), {
      wrapper: classNames(wrapClassNameExtended, modalClassNames === null || modalClassNames === void 0 ? void 0 : modalClassNames.wrapper)
    }),
    styles: Object.assign(Object.assign({}, modalContext === null || modalContext === void 0 ? void 0 : modalContext.styles), modalStyles),
    panelRef: panelRef,
    // TODO: In the future, destroyOnClose in rc-dialog needs to be upgrade to destroyOnHidden
    destroyOnClose: destroyOnHidden !== null && destroyOnHidden !== void 0 ? destroyOnHidden : destroyOnClose
  }), loading ? (/*#__PURE__*/React.createElement(Skeleton, {
    active: true,
    title: false,
    paragraph: {
      rows: 4
    },
    className: `${prefixCls}-body-skeleton`
  })) : children))));
};
export default Modal;