"use client";

import * as React from 'react';
import classNames from 'classnames';
function renderExpandIcon(locale) {
  return props => {
    const {
      prefixCls,
      onExpand,
      record,
      expanded,
      expandable
    } = props;
    const iconPrefix = `${prefixCls}-row-expand-icon`;
    return /*#__PURE__*/React.createElement("button", {
      type: "button",
      onClick: e => {
        onExpand(record, e);
        e.stopPropagation();
      },
      className: classNames(iconPrefix, {
        [`${iconPrefix}-spaced`]: !expandable,
        [`${iconPrefix}-expanded`]: expandable && expanded,
        [`${iconPrefix}-collapsed`]: expandable && !expanded
      }),
      "aria-label": expanded ? locale.collapse : locale.expand,
      "aria-expanded": expanded
    });
  };
}
export default renderExpandIcon;