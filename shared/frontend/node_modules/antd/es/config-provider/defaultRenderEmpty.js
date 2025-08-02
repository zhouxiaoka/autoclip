"use client";

import React, { useContext } from 'react';
import { ConfigContext } from '.';
import Empty from '../empty';
const DefaultRenderEmpty = props => {
  const {
    componentName
  } = props;
  const {
    getPrefixCls
  } = useContext(ConfigContext);
  const prefix = getPrefixCls('empty');
  switch (componentName) {
    case 'Table':
    case 'List':
      return /*#__PURE__*/React.createElement(Empty, {
        image: Empty.PRESENTED_IMAGE_SIMPLE
      });
    case 'Select':
    case 'TreeSelect':
    case 'Cascader':
    case 'Transfer':
    case 'Mentions':
      return /*#__PURE__*/React.createElement(Empty, {
        image: Empty.PRESENTED_IMAGE_SIMPLE,
        className: `${prefix}-small`
      });
    /**
     * This type of component should satisfy the nullish coalescing operator(??) on the left-hand side.
     * to let the component itself implement the logic.
     * For example `Table.filter`.
     */
    case 'Table.filter':
      // why `null`? legacy react16 node type `undefined` is not allowed.
      return null;
    default:
      // Should never hit if we take all the component into consider.
      return /*#__PURE__*/React.createElement(Empty, null);
  }
};
export default DefaultRenderEmpty;