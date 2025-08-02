import _typeof from "@babel/runtime/helpers/esm/typeof";
import * as React from 'react';
export default function Polite(props) {
  var visible = props.visible,
    values = props.values;
  if (!visible) {
    return null;
  }

  // Only cut part of values since it's a screen reader
  var MAX_COUNT = 50;
  return /*#__PURE__*/React.createElement("span", {
    "aria-live": "polite",
    style: {
      width: 0,
      height: 0,
      position: 'absolute',
      overflow: 'hidden',
      opacity: 0
    }
  }, "".concat(values.slice(0, MAX_COUNT).map(function (_ref) {
    var label = _ref.label,
      value = _ref.value;
    return ['number', 'string'].includes(_typeof(label)) ? label : value;
  }).join(', ')), values.length > MAX_COUNT ? ', ...' : null);
}