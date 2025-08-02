import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import _objectWithoutProperties from "@babel/runtime/helpers/esm/objectWithoutProperties";
var _excluded = ["prefixCls", "id", "inputElement", "autoFocus", "autoComplete", "editable", "activeDescendantId", "value", "open", "attrs"];
import * as React from 'react';
import classNames from 'classnames';
import { composeRef } from "rc-util/es/ref";
import { warning } from "rc-util/es/warning";
import composeProps from "rc-util/es/composeProps";
var Input = function Input(props, ref) {
  var prefixCls = props.prefixCls,
    id = props.id,
    inputElement = props.inputElement,
    autoFocus = props.autoFocus,
    autoComplete = props.autoComplete,
    editable = props.editable,
    activeDescendantId = props.activeDescendantId,
    value = props.value,
    open = props.open,
    attrs = props.attrs,
    restProps = _objectWithoutProperties(props, _excluded);
  var inputNode = inputElement || /*#__PURE__*/React.createElement("input", null);
  var _inputNode = inputNode,
    originRef = _inputNode.ref,
    originProps = _inputNode.props;
  warning(!('maxLength' in inputNode.props), "Passing 'maxLength' to input element directly may not work because input in BaseSelect is controlled.");
  inputNode = /*#__PURE__*/React.cloneElement(inputNode, _objectSpread(_objectSpread(_objectSpread({
    type: 'search'
  }, composeProps(restProps, originProps, true)), {}, {
    // Override over origin props
    id: id,
    ref: composeRef(ref, originRef),
    autoComplete: autoComplete || 'off',
    autoFocus: autoFocus,
    className: classNames("".concat(prefixCls, "-selection-search-input"), originProps === null || originProps === void 0 ? void 0 : originProps.className),
    role: 'combobox',
    'aria-expanded': open || false,
    'aria-haspopup': 'listbox',
    'aria-owns': "".concat(id, "_list"),
    'aria-autocomplete': 'list',
    'aria-controls': "".concat(id, "_list"),
    'aria-activedescendant': open ? activeDescendantId : undefined
  }, attrs), {}, {
    value: editable ? value : '',
    readOnly: !editable,
    unselectable: !editable ? 'on' : null,
    style: _objectSpread(_objectSpread({}, originProps.style), {}, {
      opacity: editable ? null : 0
    })
  }));
  return inputNode;
};
var RefInput = /*#__PURE__*/React.forwardRef(Input);
if (process.env.NODE_ENV !== 'production') {
  RefInput.displayName = 'Input';
}
export default RefInput;