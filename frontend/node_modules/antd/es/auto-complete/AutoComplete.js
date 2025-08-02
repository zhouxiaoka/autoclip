"use client";

import * as React from 'react';
import cls from 'classnames';
import toArray from "rc-util/es/Children/toArray";
import omit from "rc-util/es/omit";
import { useZIndex } from '../_util/hooks/useZIndex';
import { devUseWarning } from '../_util/warning';
import { ConfigContext } from '../config-provider';
import Select from '../select';
const {
  Option
} = Select;
function isSelectOptionOrSelectOptGroup(child) {
  return (child === null || child === void 0 ? void 0 : child.type) && (child.type.isSelectOption || child.type.isSelectOptGroup);
}
const AutoComplete = (props, ref) => {
  var _a, _b;
  const {
    prefixCls: customizePrefixCls,
    className,
    popupClassName,
    dropdownClassName,
    children,
    dataSource,
    dropdownStyle,
    dropdownRender,
    popupRender,
    onDropdownVisibleChange,
    onOpenChange,
    styles,
    classNames
  } = props;
  const childNodes = toArray(children);
  const mergedPopupStyle = ((_a = styles === null || styles === void 0 ? void 0 : styles.popup) === null || _a === void 0 ? void 0 : _a.root) || dropdownStyle;
  const mergedPopupClassName = ((_b = classNames === null || classNames === void 0 ? void 0 : classNames.popup) === null || _b === void 0 ? void 0 : _b.root) || popupClassName || dropdownClassName;
  const mergedPopupRender = popupRender || dropdownRender;
  const mergedOnOpenChange = onOpenChange || onDropdownVisibleChange;
  // ============================= Input =============================
  let customizeInput;
  if (childNodes.length === 1 && /*#__PURE__*/React.isValidElement(childNodes[0]) && !isSelectOptionOrSelectOptGroup(childNodes[0])) {
    [customizeInput] = childNodes;
  }
  const getInputElement = customizeInput ? () => customizeInput : undefined;
  // ============================ Options ============================
  let optionChildren;
  // [Legacy] convert `children` or `dataSource` into option children
  if (childNodes.length && isSelectOptionOrSelectOptGroup(childNodes[0])) {
    optionChildren = children;
  } else {
    optionChildren = dataSource ? dataSource.map(item => {
      if (/*#__PURE__*/React.isValidElement(item)) {
        return item;
      }
      switch (typeof item) {
        case 'string':
          return /*#__PURE__*/React.createElement(Option, {
            key: item,
            value: item
          }, item);
        case 'object':
          {
            const {
              value: optionValue
            } = item;
            return /*#__PURE__*/React.createElement(Option, {
              key: optionValue,
              value: optionValue
            }, item.text);
          }
        default:
          return undefined;
      }
    }) : [];
  }
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('AutoComplete');
    process.env.NODE_ENV !== "production" ? warning(!customizeInput || !('size' in props), 'usage', 'You need to control style self instead of setting `size` when using customize input.') : void 0;
    const deprecatedProps = {
      dropdownMatchSelectWidth: 'popupMatchSelectWidth',
      dropdownStyle: 'styles.popup.root',
      dropdownClassName: 'classNames.popup.root',
      popupClassName: 'classNames.popup.root',
      dropdownRender: 'popupRender',
      onDropdownVisibleChange: 'onOpenChange',
      dataSource: 'options'
    };
    Object.entries(deprecatedProps).forEach(([oldProp, newProp]) => {
      warning.deprecated(!(oldProp in props), oldProp, newProp);
    });
  }
  const {
    getPrefixCls
  } = React.useContext(ConfigContext);
  const prefixCls = getPrefixCls('select', customizePrefixCls);
  // ============================ zIndex ============================
  const [zIndex] = useZIndex('SelectLike', mergedPopupStyle === null || mergedPopupStyle === void 0 ? void 0 : mergedPopupStyle.zIndex);
  return /*#__PURE__*/React.createElement(Select, Object.assign({
    ref: ref,
    suffixIcon: null
  }, omit(props, ['dataSource', 'dropdownClassName', 'popupClassName']), {
    prefixCls: prefixCls,
    classNames: {
      popup: {
        root: mergedPopupClassName
      },
      root: classNames === null || classNames === void 0 ? void 0 : classNames.root
    },
    styles: {
      popup: {
        root: Object.assign(Object.assign({}, mergedPopupStyle), {
          zIndex
        })
      },
      root: styles === null || styles === void 0 ? void 0 : styles.root
    },
    className: cls(`${prefixCls}-auto-complete`, className),
    mode: Select.SECRET_COMBOBOX_MODE_DO_NOT_USE,
    popupRender: mergedPopupRender,
    onOpenChange: mergedOnOpenChange,
    // Internal api
    getInputElement
  }), optionChildren);
};
const RefAutoComplete = /*#__PURE__*/React.forwardRef(AutoComplete);
if (process.env.NODE_ENV !== 'production') {
  RefAutoComplete.displayName = 'AutoComplete';
}
export default RefAutoComplete;