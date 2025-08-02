"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = Checkbox;
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _context = _interopRequireDefault(require("../context"));
function Checkbox(_ref) {
  var _classNames;
  var prefixCls = _ref.prefixCls,
    checked = _ref.checked,
    halfChecked = _ref.halfChecked,
    disabled = _ref.disabled,
    onClick = _ref.onClick,
    disableCheckbox = _ref.disableCheckbox;
  var _React$useContext = React.useContext(_context.default),
    checkable = _React$useContext.checkable;
  var customCheckbox = typeof checkable !== 'boolean' ? checkable : null;
  return /*#__PURE__*/React.createElement("span", {
    className: (0, _classnames.default)("".concat(prefixCls), (_classNames = {}, (0, _defineProperty2.default)(_classNames, "".concat(prefixCls, "-checked"), checked), (0, _defineProperty2.default)(_classNames, "".concat(prefixCls, "-indeterminate"), !checked && halfChecked), (0, _defineProperty2.default)(_classNames, "".concat(prefixCls, "-disabled"), disabled || disableCheckbox), _classNames)),
    onClick: onClick
  }, customCheckbox);
}