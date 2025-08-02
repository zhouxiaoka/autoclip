import _defineProperty from "@babel/runtime/helpers/esm/defineProperty";
import classNames from 'classnames';
import * as React from 'react';
import { genDataNodeKey, getRemovable } from "../util";
var TabNode = function TabNode(props) {
  var prefixCls = props.prefixCls,
    id = props.id,
    active = props.active,
    focus = props.focus,
    _props$tab = props.tab,
    key = _props$tab.key,
    label = _props$tab.label,
    disabled = _props$tab.disabled,
    closeIcon = _props$tab.closeIcon,
    icon = _props$tab.icon,
    closable = props.closable,
    renderWrapper = props.renderWrapper,
    removeAriaLabel = props.removeAriaLabel,
    editable = props.editable,
    onClick = props.onClick,
    onFocus = props.onFocus,
    onBlur = props.onBlur,
    onKeyDown = props.onKeyDown,
    onMouseDown = props.onMouseDown,
    onMouseUp = props.onMouseUp,
    style = props.style,
    tabCount = props.tabCount,
    currentPosition = props.currentPosition;
  var tabPrefix = "".concat(prefixCls, "-tab");
  var removable = getRemovable(closable, closeIcon, editable, disabled);
  function onInternalClick(e) {
    if (disabled) {
      return;
    }
    onClick(e);
  }
  function onRemoveTab(event) {
    event.preventDefault();
    event.stopPropagation();
    editable.onEdit('remove', {
      key: key,
      event: event
    });
  }
  var labelNode = React.useMemo(function () {
    return icon && typeof label === 'string' ? /*#__PURE__*/React.createElement("span", null, label) : label;
  }, [label, icon]);
  var btnRef = React.useRef(null);
  React.useEffect(function () {
    if (focus && btnRef.current) {
      btnRef.current.focus();
    }
  }, [focus]);
  var node = /*#__PURE__*/React.createElement("div", {
    key: key,
    "data-node-key": genDataNodeKey(key),
    className: classNames(tabPrefix, _defineProperty(_defineProperty(_defineProperty(_defineProperty({}, "".concat(tabPrefix, "-with-remove"), removable), "".concat(tabPrefix, "-active"), active), "".concat(tabPrefix, "-disabled"), disabled), "".concat(tabPrefix, "-focus"), focus)),
    style: style,
    onClick: onInternalClick
  }, /*#__PURE__*/React.createElement("div", {
    ref: btnRef,
    role: "tab",
    "aria-selected": active,
    id: id && "".concat(id, "-tab-").concat(key),
    className: "".concat(tabPrefix, "-btn"),
    "aria-controls": id && "".concat(id, "-panel-").concat(key),
    "aria-disabled": disabled,
    tabIndex: disabled ? null : active ? 0 : -1,
    onClick: function onClick(e) {
      e.stopPropagation();
      onInternalClick(e);
    },
    onKeyDown: onKeyDown,
    onMouseDown: onMouseDown,
    onMouseUp: onMouseUp,
    onFocus: onFocus,
    onBlur: onBlur
  }, focus && /*#__PURE__*/React.createElement("div", {
    "aria-live": "polite",
    style: {
      width: 0,
      height: 0,
      position: 'absolute',
      overflow: 'hidden',
      opacity: 0
    }
  }, "Tab ".concat(currentPosition, " of ").concat(tabCount)), icon && /*#__PURE__*/React.createElement("span", {
    className: "".concat(tabPrefix, "-icon")
  }, icon), label && labelNode), removable && /*#__PURE__*/React.createElement("button", {
    type: "button",
    role: "tab",
    "aria-label": removeAriaLabel || 'remove',
    tabIndex: active ? 0 : -1,
    className: "".concat(tabPrefix, "-remove"),
    onClick: function onClick(e) {
      e.stopPropagation();
      onRemoveTab(e);
    }
  }, closeIcon || editable.removeIcon || '×'));
  return renderWrapper ? renderWrapper(node) : node;
};
export default TabNode;