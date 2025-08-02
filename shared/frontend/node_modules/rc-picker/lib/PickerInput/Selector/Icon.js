"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.ClearIcon = ClearIcon;
exports.default = Icon;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _objectWithoutProperties2 = _interopRequireDefault(require("@babel/runtime/helpers/objectWithoutProperties"));
var React = _interopRequireWildcard(require("react"));
var _context = _interopRequireDefault(require("../context"));
var _excluded = ["icon", "type"],
  _excluded2 = ["onClear"];
function Icon(props) {
  var icon = props.icon,
    type = props.type,
    restProps = (0, _objectWithoutProperties2.default)(props, _excluded);
  var _React$useContext = React.useContext(_context.default),
    prefixCls = _React$useContext.prefixCls;
  return icon ? /*#__PURE__*/React.createElement("span", (0, _extends2.default)({
    className: "".concat(prefixCls, "-").concat(type)
  }, restProps), icon) : null;
}
function ClearIcon(_ref) {
  var onClear = _ref.onClear,
    restProps = (0, _objectWithoutProperties2.default)(_ref, _excluded2);
  return /*#__PURE__*/React.createElement(Icon, (0, _extends2.default)({}, restProps, {
    type: "clear",
    role: "button",
    onMouseDown: function onMouseDown(e) {
      e.preventDefault();
    },
    onClick: function onClick(e) {
      e.stopPropagation();
      onClear();
    }
  }));
}