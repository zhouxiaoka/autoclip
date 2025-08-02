import _defineProperty from "@babel/runtime/helpers/esm/defineProperty";
import _slicedToArray from "@babel/runtime/helpers/esm/slicedToArray";
import classnames from 'classnames';
import React from 'react';
var PanelContent = /*#__PURE__*/React.forwardRef(function (props, ref) {
  var prefixCls = props.prefixCls,
    forceRender = props.forceRender,
    className = props.className,
    style = props.style,
    children = props.children,
    isActive = props.isActive,
    role = props.role,
    customizeClassNames = props.classNames,
    styles = props.styles;
  var _React$useState = React.useState(isActive || forceRender),
    _React$useState2 = _slicedToArray(_React$useState, 2),
    rendered = _React$useState2[0],
    setRendered = _React$useState2[1];
  React.useEffect(function () {
    if (forceRender || isActive) {
      setRendered(true);
    }
  }, [forceRender, isActive]);
  if (!rendered) {
    return null;
  }
  return /*#__PURE__*/React.createElement("div", {
    ref: ref,
    className: classnames("".concat(prefixCls, "-content"), _defineProperty(_defineProperty({}, "".concat(prefixCls, "-content-active"), isActive), "".concat(prefixCls, "-content-inactive"), !isActive), className),
    style: style,
    role: role
  }, /*#__PURE__*/React.createElement("div", {
    className: classnames("".concat(prefixCls, "-content-box"), customizeClassNames === null || customizeClassNames === void 0 ? void 0 : customizeClassNames.body),
    style: styles === null || styles === void 0 ? void 0 : styles.body
  }, children));
});
PanelContent.displayName = 'PanelContent';
export default PanelContent;