import _extends from "@babel/runtime/helpers/esm/extends";
import _objectWithoutProperties from "@babel/runtime/helpers/esm/objectWithoutProperties";
var _excluded = ["className", "title", "eventKey", "children"];
import classNames from 'classnames';
import omit from "rc-util/es/omit";
import * as React from 'react';
import { MenuContext } from "./context/MenuContext";
import { useFullPath, useMeasure } from "./context/PathContext";
import { parseChildren } from "./utils/commonUtil";
var InternalMenuItemGroup = /*#__PURE__*/React.forwardRef(function (props, ref) {
  var className = props.className,
    title = props.title,
    eventKey = props.eventKey,
    children = props.children,
    restProps = _objectWithoutProperties(props, _excluded);
  var _React$useContext = React.useContext(MenuContext),
    prefixCls = _React$useContext.prefixCls;
  var groupPrefixCls = "".concat(prefixCls, "-item-group");
  return /*#__PURE__*/React.createElement("li", _extends({
    ref: ref,
    role: "presentation"
  }, restProps, {
    onClick: function onClick(e) {
      return e.stopPropagation();
    },
    className: classNames(groupPrefixCls, className)
  }), /*#__PURE__*/React.createElement("div", {
    role: "presentation",
    className: "".concat(groupPrefixCls, "-title"),
    title: typeof title === 'string' ? title : undefined
  }, title), /*#__PURE__*/React.createElement("ul", {
    role: "group",
    className: "".concat(groupPrefixCls, "-list")
  }, children));
});
var MenuItemGroup = /*#__PURE__*/React.forwardRef(function (props, ref) {
  var eventKey = props.eventKey,
    children = props.children;
  var connectedKeyPath = useFullPath(eventKey);
  var childList = parseChildren(children, connectedKeyPath);
  var measure = useMeasure();
  if (measure) {
    return childList;
  }
  return /*#__PURE__*/React.createElement(InternalMenuItemGroup, _extends({
    ref: ref
  }, omit(props, ['warnKey'])), childList);
});
if (process.env.NODE_ENV !== 'production') {
  MenuItemGroup.displayName = 'MenuItemGroup';
}
export default MenuItemGroup;