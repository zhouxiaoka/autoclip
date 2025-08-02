import React, { forwardRef } from 'react';
var Transform = /*#__PURE__*/forwardRef(function (props, ref) {
  var children = props.children,
    x = props.x,
    y = props.y;
  return /*#__PURE__*/React.createElement("div", {
    ref: ref,
    style: {
      position: 'absolute',
      left: "".concat(x, "%"),
      top: "".concat(y, "%"),
      zIndex: 1,
      transform: 'translate(-50%, -50%)'
    }
  }, children);
});
export default Transform;