"use client";

import * as React from 'react';
import classNames from 'classnames';
import { Item } from 'rc-menu';
import toArray from "rc-util/es/Children/toArray";
import omit from "rc-util/es/omit";
import { cloneElement } from '../_util/reactNode';
import { SiderContext } from '../layout/Sider';
import Tooltip from '../tooltip';
import MenuContext from './MenuContext';
const MenuItem = props => {
  var _a;
  const {
    className,
    children,
    icon,
    title,
    danger,
    extra
  } = props;
  const {
    prefixCls,
    firstLevel,
    direction,
    disableMenuItemTitleTooltip,
    inlineCollapsed: isInlineCollapsed
  } = React.useContext(MenuContext);
  const renderItemChildren = inlineCollapsed => {
    const label = children === null || children === void 0 ? void 0 : children[0];
    const wrapNode = /*#__PURE__*/React.createElement("span", {
      className: classNames(`${prefixCls}-title-content`, {
        [`${prefixCls}-title-content-with-extra`]: !!extra || extra === 0
      })
    }, children);
    // inline-collapsed.md demo 依赖 span 来隐藏文字,有 icon 属性，则内部包裹一个 span
    // ref: https://github.com/ant-design/ant-design/pull/23456
    if (!icon || /*#__PURE__*/React.isValidElement(children) && children.type === 'span') {
      if (children && inlineCollapsed && firstLevel && typeof label === 'string') {
        return /*#__PURE__*/React.createElement("div", {
          className: `${prefixCls}-inline-collapsed-noicon`
        }, label.charAt(0));
      }
    }
    return wrapNode;
  };
  const {
    siderCollapsed
  } = React.useContext(SiderContext);
  let tooltipTitle = title;
  if (typeof title === 'undefined') {
    tooltipTitle = firstLevel ? children : '';
  } else if (title === false) {
    tooltipTitle = '';
  }
  const tooltipProps = {
    title: tooltipTitle
  };
  if (!siderCollapsed && !isInlineCollapsed) {
    tooltipProps.title = null;
    // Reset `open` to fix control mode tooltip display not correct
    // ref: https://github.com/ant-design/ant-design/issues/16742
    tooltipProps.open = false;
  }
  const childrenLength = toArray(children).length;
  let returnNode = /*#__PURE__*/React.createElement(Item, Object.assign({}, omit(props, ['title', 'icon', 'danger']), {
    className: classNames({
      [`${prefixCls}-item-danger`]: danger,
      [`${prefixCls}-item-only-child`]: (icon ? childrenLength + 1 : childrenLength) === 1
    }, className),
    title: typeof title === 'string' ? title : undefined
  }), cloneElement(icon, {
    className: classNames(/*#__PURE__*/React.isValidElement(icon) ? (_a = icon.props) === null || _a === void 0 ? void 0 : _a.className : '', `${prefixCls}-item-icon`)
  }), renderItemChildren(isInlineCollapsed));
  if (!disableMenuItemTitleTooltip) {
    returnNode = /*#__PURE__*/React.createElement(Tooltip, Object.assign({}, tooltipProps, {
      placement: direction === 'rtl' ? 'left' : 'right',
      classNames: {
        root: `${prefixCls}-inline-collapsed-tooltip`
      }
    }), returnNode);
  }
  return returnNode;
};
export default MenuItem;