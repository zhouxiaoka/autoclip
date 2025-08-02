"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireWildcard(require("react"));
var _Input = _interopRequireDefault(require("../../input/Input"));
var _color = require("../color");
var _util = require("../util");
const hexReg = /(^#[\da-f]{6}$)|(^#[\da-f]{8}$)/i;
const isHexString = hex => hexReg.test(`#${hex}`);
const ColorHexInput = ({
  prefixCls,
  value,
  onChange
}) => {
  const colorHexInputPrefixCls = `${prefixCls}-hex-input`;
  const [hexValue, setHexValue] = (0, _react.useState)(() => value ? (0, _color.toHexFormat)(value.toHexString()) : undefined);
  // Update step value
  (0, _react.useEffect)(() => {
    if (value) {
      setHexValue((0, _color.toHexFormat)(value.toHexString()));
    }
  }, [value]);
  const handleHexChange = e => {
    const originValue = e.target.value;
    setHexValue((0, _color.toHexFormat)(originValue));
    if (isHexString((0, _color.toHexFormat)(originValue, true))) {
      onChange === null || onChange === void 0 ? void 0 : onChange((0, _util.generateColor)(originValue));
    }
  };
  return /*#__PURE__*/_react.default.createElement(_Input.default, {
    className: colorHexInputPrefixCls,
    value: hexValue,
    prefix: "#",
    onChange: handleHexChange,
    size: "small"
  });
};
var _default = exports.default = ColorHexInput;