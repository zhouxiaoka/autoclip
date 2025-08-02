"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import React, { Children, useContext } from 'react';
import classNames from 'classnames';
import { cloneElement } from '../_util/reactNode';
import { ConfigContext } from '../config-provider';
import { Col } from '../grid';
import { ListContext } from './context';
export const Meta = _a => {
  var {
      prefixCls: customizePrefixCls,
      className,
      avatar,
      title,
      description
    } = _a,
    others = __rest(_a, ["prefixCls", "className", "avatar", "title", "description"]);
  const {
    getPrefixCls
  } = useContext(ConfigContext);
  const prefixCls = getPrefixCls('list', customizePrefixCls);
  const classString = classNames(`${prefixCls}-item-meta`, className);
  const content = /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-item-meta-content`
  }, title && /*#__PURE__*/React.createElement("h4", {
    className: `${prefixCls}-item-meta-title`
  }, title), description && /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-item-meta-description`
  }, description));
  return /*#__PURE__*/React.createElement("div", Object.assign({}, others, {
    className: classString
  }), avatar && /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-item-meta-avatar`
  }, avatar), (title || description) && content);
};
const InternalItem = /*#__PURE__*/React.forwardRef((props, ref) => {
  const {
      prefixCls: customizePrefixCls,
      children,
      actions,
      extra,
      styles,
      className,
      classNames: customizeClassNames,
      colStyle
    } = props,
    others = __rest(props, ["prefixCls", "children", "actions", "extra", "styles", "className", "classNames", "colStyle"]);
  const {
    grid,
    itemLayout
  } = useContext(ListContext);
  const {
    getPrefixCls,
    list
  } = useContext(ConfigContext);
  const moduleClass = moduleName => {
    var _a, _b;
    return classNames((_b = (_a = list === null || list === void 0 ? void 0 : list.item) === null || _a === void 0 ? void 0 : _a.classNames) === null || _b === void 0 ? void 0 : _b[moduleName], customizeClassNames === null || customizeClassNames === void 0 ? void 0 : customizeClassNames[moduleName]);
  };
  const moduleStyle = moduleName => {
    var _a, _b;
    return Object.assign(Object.assign({}, (_b = (_a = list === null || list === void 0 ? void 0 : list.item) === null || _a === void 0 ? void 0 : _a.styles) === null || _b === void 0 ? void 0 : _b[moduleName]), styles === null || styles === void 0 ? void 0 : styles[moduleName]);
  };
  const isItemContainsTextNodeAndNotSingular = () => {
    let result = false;
    Children.forEach(children, element => {
      if (typeof element === 'string') {
        result = true;
      }
    });
    return result && Children.count(children) > 1;
  };
  const isFlexMode = () => {
    if (itemLayout === 'vertical') {
      return !!extra;
    }
    return !isItemContainsTextNodeAndNotSingular();
  };
  const prefixCls = getPrefixCls('list', customizePrefixCls);
  const actionsContent = actions && actions.length > 0 && (/*#__PURE__*/React.createElement("ul", {
    className: classNames(`${prefixCls}-item-action`, moduleClass('actions')),
    key: "actions",
    style: moduleStyle('actions')
  }, actions.map((action, i) => (
  /*#__PURE__*/
  // eslint-disable-next-line react/no-array-index-key
  React.createElement("li", {
    key: `${prefixCls}-item-action-${i}`
  }, action, i !== actions.length - 1 && /*#__PURE__*/React.createElement("em", {
    className: `${prefixCls}-item-action-split`
  }))))));
  const Element = grid ? 'div' : 'li';
  const itemChildren = /*#__PURE__*/React.createElement(Element, Object.assign({}, others, !grid ? {
    ref
  } : {}, {
    className: classNames(`${prefixCls}-item`, {
      [`${prefixCls}-item-no-flex`]: !isFlexMode()
    }, className)
  }), itemLayout === 'vertical' && extra ? [/*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-item-main`,
    key: "content"
  }, children, actionsContent), /*#__PURE__*/React.createElement("div", {
    className: classNames(`${prefixCls}-item-extra`, moduleClass('extra')),
    key: "extra",
    style: moduleStyle('extra')
  }, extra)] : [children, actionsContent, cloneElement(extra, {
    key: 'extra'
  })]);
  return grid ? (/*#__PURE__*/React.createElement(Col, {
    ref: ref,
    flex: 1,
    style: colStyle
  }, itemChildren)) : itemChildren;
});
const Item = InternalItem;
Item.Meta = Meta;
export default Item;