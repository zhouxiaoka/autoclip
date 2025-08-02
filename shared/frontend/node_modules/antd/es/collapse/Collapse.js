"use client";

import * as React from 'react';
import RightOutlined from "@ant-design/icons/es/icons/RightOutlined";
import classNames from 'classnames';
import RcCollapse from 'rc-collapse';
import toArray from "rc-util/es/Children/toArray";
import omit from "rc-util/es/omit";
import initCollapseMotion from '../_util/motion';
import { cloneElement } from '../_util/reactNode';
import { devUseWarning } from '../_util/warning';
import { useComponentConfig } from '../config-provider/context';
import useSize from '../config-provider/hooks/useSize';
import CollapsePanel from './CollapsePanel';
import useStyle from './style';
const Collapse = /*#__PURE__*/React.forwardRef((props, ref) => {
  const {
    getPrefixCls,
    direction,
    expandIcon: contextExpandIcon,
    className: contextClassName,
    style: contextStyle
  } = useComponentConfig('collapse');
  const {
    prefixCls: customizePrefixCls,
    className,
    rootClassName,
    style,
    bordered = true,
    ghost,
    size: customizeSize,
    expandIconPosition = 'start',
    children,
    destroyInactivePanel,
    destroyOnHidden,
    expandIcon
  } = props;
  const mergedSize = useSize(ctx => {
    var _a;
    return (_a = customizeSize !== null && customizeSize !== void 0 ? customizeSize : ctx) !== null && _a !== void 0 ? _a : 'middle';
  });
  const prefixCls = getPrefixCls('collapse', customizePrefixCls);
  const rootPrefixCls = getPrefixCls();
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls);
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Collapse');
    // Warning if use legacy type `expandIconPosition`
    process.env.NODE_ENV !== "production" ? warning(expandIconPosition !== 'left' && expandIconPosition !== 'right', 'deprecated', '`expandIconPosition` with `left` or `right` is deprecated. Please use `start` or `end` instead.') : void 0;
    warning.deprecated(!('destroyInactivePanel' in props), 'destroyInactivePanel', 'destroyOnHidden');
  }
  // Align with logic position
  const mergedExpandIconPosition = React.useMemo(() => {
    if (expandIconPosition === 'left') {
      return 'start';
    }
    return expandIconPosition === 'right' ? 'end' : expandIconPosition;
  }, [expandIconPosition]);
  const mergedExpandIcon = expandIcon !== null && expandIcon !== void 0 ? expandIcon : contextExpandIcon;
  const renderExpandIcon = React.useCallback((panelProps = {}) => {
    const icon = typeof mergedExpandIcon === 'function' ? mergedExpandIcon(panelProps) : (/*#__PURE__*/React.createElement(RightOutlined, {
      rotate: panelProps.isActive ? direction === 'rtl' ? -90 : 90 : undefined,
      "aria-label": panelProps.isActive ? 'expanded' : 'collapsed'
    }));
    return cloneElement(icon, () => {
      var _a;
      return {
        className: classNames((_a = icon === null || icon === void 0 ? void 0 : icon.props) === null || _a === void 0 ? void 0 : _a.className, `${prefixCls}-arrow`)
      };
    });
  }, [mergedExpandIcon, prefixCls]);
  const collapseClassName = classNames(`${prefixCls}-icon-position-${mergedExpandIconPosition}`, {
    [`${prefixCls}-borderless`]: !bordered,
    [`${prefixCls}-rtl`]: direction === 'rtl',
    [`${prefixCls}-ghost`]: !!ghost,
    [`${prefixCls}-${mergedSize}`]: mergedSize !== 'middle'
  }, contextClassName, className, rootClassName, hashId, cssVarCls);
  const openMotion = Object.assign(Object.assign({}, initCollapseMotion(rootPrefixCls)), {
    motionAppear: false,
    leavedClassName: `${prefixCls}-content-hidden`
  });
  const items = React.useMemo(() => {
    if (children) {
      return toArray(children).map((child, index) => {
        var _a, _b;
        const childProps = child.props;
        if (childProps === null || childProps === void 0 ? void 0 : childProps.disabled) {
          const key = (_a = child.key) !== null && _a !== void 0 ? _a : String(index);
          const mergedChildProps = Object.assign(Object.assign({}, omit(child.props, ['disabled'])), {
            key,
            collapsible: (_b = childProps.collapsible) !== null && _b !== void 0 ? _b : 'disabled'
          });
          return cloneElement(child, mergedChildProps);
        }
        return child;
      });
    }
    return null;
  }, [children]);
  return wrapCSSVar(
  /*#__PURE__*/
  // @ts-ignore
  React.createElement(RcCollapse, Object.assign({
    ref: ref,
    openMotion: openMotion
  }, omit(props, ['rootClassName']), {
    expandIcon: renderExpandIcon,
    prefixCls: prefixCls,
    className: collapseClassName,
    style: Object.assign(Object.assign({}, contextStyle), style),
    // TODO: In the future, destroyInactivePanel in rc-collapse needs to be upgrade to destroyOnHidden
    destroyInactivePanel: destroyOnHidden !== null && destroyOnHidden !== void 0 ? destroyOnHidden : destroyInactivePanel
  }), items));
});
if (process.env.NODE_ENV !== 'production') {
  Collapse.displayName = 'Collapse';
}
export default Object.assign(Collapse, {
  Panel: CollapsePanel
});