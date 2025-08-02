"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _SearchOutlined = _interopRequireDefault(require("@ant-design/icons/SearchOutlined"));
var _Input = _interopRequireDefault(require("../input/Input"));
const Search = props => {
  const {
    placeholder = '',
    value,
    prefixCls,
    disabled,
    onChange,
    handleClear
  } = props;
  const handleChange = React.useCallback(e => {
    onChange === null || onChange === void 0 ? void 0 : onChange(e);
    if (e.target.value === '') {
      handleClear === null || handleClear === void 0 ? void 0 : handleClear();
    }
  }, [onChange]);
  return /*#__PURE__*/React.createElement(_Input.default, {
    placeholder: placeholder,
    className: prefixCls,
    value: value,
    onChange: handleChange,
    disabled: disabled,
    allowClear: true,
    prefix: /*#__PURE__*/React.createElement(_SearchOutlined.default, null)
  });
};
if (process.env.NODE_ENV !== 'production') {
  Search.displayName = 'Search';
}
var _default = exports.default = Search;