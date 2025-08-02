import classNames from 'classnames';
import * as React from 'react';
export default function Popup(props) {
  var children = props.children,
    prefixCls = props.prefixCls,
    id = props.id,
    innerStyle = props.overlayInnerStyle,
    bodyClassName = props.bodyClassName,
    className = props.className,
    style = props.style;
  return /*#__PURE__*/React.createElement("div", {
    className: classNames("".concat(prefixCls, "-content"), className),
    style: style
  }, /*#__PURE__*/React.createElement("div", {
    className: classNames("".concat(prefixCls, "-inner"), bodyClassName),
    id: id,
    role: "tooltip",
    style: innerStyle
  }, typeof children === 'function' ? children() : children));
}