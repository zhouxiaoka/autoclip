"use client";

import * as React from 'react';
import Cell from './Cell';
import DescriptionsContext from './DescriptionsContext';
function renderCells(items, {
  colon,
  prefixCls,
  bordered
}, {
  component,
  type,
  showLabel,
  showContent,
  labelStyle: rootLabelStyle,
  contentStyle: rootContentStyle,
  styles: rootStyles
}) {
  return items.map(({
    label,
    children,
    prefixCls: itemPrefixCls = prefixCls,
    className,
    style,
    labelStyle,
    contentStyle,
    span = 1,
    key,
    styles
  }, index) => {
    if (typeof component === 'string') {
      return /*#__PURE__*/React.createElement(Cell, {
        key: `${type}-${key || index}`,
        className: className,
        style: style,
        styles: {
          label: Object.assign(Object.assign(Object.assign(Object.assign({}, rootLabelStyle), rootStyles === null || rootStyles === void 0 ? void 0 : rootStyles.label), labelStyle), styles === null || styles === void 0 ? void 0 : styles.label),
          content: Object.assign(Object.assign(Object.assign(Object.assign({}, rootContentStyle), rootStyles === null || rootStyles === void 0 ? void 0 : rootStyles.content), contentStyle), styles === null || styles === void 0 ? void 0 : styles.content)
        },
        span: span,
        colon: colon,
        component: component,
        itemPrefixCls: itemPrefixCls,
        bordered: bordered,
        label: showLabel ? label : null,
        content: showContent ? children : null,
        type: type
      });
    }
    return [/*#__PURE__*/React.createElement(Cell, {
      key: `label-${key || index}`,
      className: className,
      style: Object.assign(Object.assign(Object.assign(Object.assign(Object.assign({}, rootLabelStyle), rootStyles === null || rootStyles === void 0 ? void 0 : rootStyles.label), style), labelStyle), styles === null || styles === void 0 ? void 0 : styles.label),
      span: 1,
      colon: colon,
      component: component[0],
      itemPrefixCls: itemPrefixCls,
      bordered: bordered,
      label: label,
      type: "label"
    }), /*#__PURE__*/React.createElement(Cell, {
      key: `content-${key || index}`,
      className: className,
      style: Object.assign(Object.assign(Object.assign(Object.assign(Object.assign({}, rootContentStyle), rootStyles === null || rootStyles === void 0 ? void 0 : rootStyles.content), style), contentStyle), styles === null || styles === void 0 ? void 0 : styles.content),
      span: span * 2 - 1,
      component: component[1],
      itemPrefixCls: itemPrefixCls,
      bordered: bordered,
      content: children,
      type: "content"
    })];
  });
}
const Row = props => {
  const descContext = React.useContext(DescriptionsContext);
  const {
    prefixCls,
    vertical,
    row,
    index,
    bordered
  } = props;
  if (vertical) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("tr", {
      key: `label-${index}`,
      className: `${prefixCls}-row`
    }, renderCells(row, props, Object.assign({
      component: 'th',
      type: 'label',
      showLabel: true
    }, descContext))), /*#__PURE__*/React.createElement("tr", {
      key: `content-${index}`,
      className: `${prefixCls}-row`
    }, renderCells(row, props, Object.assign({
      component: 'td',
      type: 'content',
      showContent: true
    }, descContext))));
  }
  return /*#__PURE__*/React.createElement("tr", {
    key: index,
    className: `${prefixCls}-row`
  }, renderCells(row, props, Object.assign({
    component: bordered ? ['th', 'td'] : 'td',
    type: 'item',
    showLabel: true,
    showContent: true
  }, descContext)));
};
export default Row;