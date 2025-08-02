"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _inputNumber = _interopRequireDefault(require("../../input-number"));
const ColorSteppers = ({
  prefixCls,
  min = 0,
  max = 100,
  value,
  onChange,
  className,
  formatter
}) => {
  const colorSteppersPrefixCls = `${prefixCls}-steppers`;
  const [internalValue, setInternalValue] = (0, _react.useState)(0);
  const stepValue = !Number.isNaN(value) ? value : internalValue;
  return /*#__PURE__*/_react.default.createElement(_inputNumber.default, {
    className: (0, _classnames.default)(colorSteppersPrefixCls, className),
    min: min,
    max: max,
    value: stepValue,
    formatter: formatter,
    size: "small",
    onChange: step => {
      setInternalValue(step || 0);
      onChange === null || onChange === void 0 ? void 0 : onChange(step);
    }
  });
};
var _default = exports.default = ColorSteppers;