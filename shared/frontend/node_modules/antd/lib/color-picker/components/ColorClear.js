"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireDefault(require("react"));
var _util = require("../util");
const ColorClear = ({
  prefixCls,
  value,
  onChange
}) => {
  const handleClick = () => {
    if (onChange && value && !value.cleared) {
      const hsba = value.toHsb();
      hsba.a = 0;
      const genColor = (0, _util.generateColor)(hsba);
      genColor.cleared = true;
      onChange(genColor);
    }
  };
  return /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-clear`,
    onClick: handleClick
  });
};
var _default = exports.default = ColorClear;