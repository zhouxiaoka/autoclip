"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireDefault(require("react"));
var DropIndicator = function DropIndicator(props) {
  var dropPosition = props.dropPosition,
    dropLevelOffset = props.dropLevelOffset,
    indent = props.indent;
  var style = {
    pointerEvents: 'none',
    position: 'absolute',
    right: 0,
    backgroundColor: 'red',
    height: 2
  };
  switch (dropPosition) {
    case -1:
      style.top = 0;
      style.left = -dropLevelOffset * indent;
      break;
    case 1:
      style.bottom = 0;
      style.left = -dropLevelOffset * indent;
      break;
    case 0:
      style.bottom = 0;
      style.left = indent;
      break;
  }
  return /*#__PURE__*/_react.default.createElement("div", {
    style: style
  });
};
if (process.env.NODE_ENV !== 'production') {
  DropIndicator.displayName = 'DropIndicator';
}
var _default = exports.default = DropIndicator;