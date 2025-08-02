"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _SwitcherOutlined = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/SwitcherOutlined"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var SwitcherOutlined = function SwitcherOutlined(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _SwitcherOutlined.default
  }));
};

/**![switcher](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjY0IDY0IDg5NiA4OTYiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTc1MiAyNDBIMTQ0Yy0xNy43IDAtMzIgMTQuMy0zMiAzMnY2MDhjMCAxNy43IDE0LjMgMzIgMzIgMzJoNjA4YzE3LjcgMCAzMi0xNC4zIDMyLTMyVjI3MmMwLTE3LjctMTQuMy0zMi0zMi0zMnptLTQwIDYwMEgxODRWMzEyaDUyOHY1Mjh6bTE2OC03MjhIMjY0Yy00LjQgMC04IDMuNi04IDh2NTZjMCA0LjQgMy42IDggOCA4aDU3NnY1NzZjMCA0LjQgMy42IDggOCA4aDU2YzQuNCAwIDgtMy42IDgtOFYxNDRjMC0xNy43LTE0LjMtMzItMzItMzJ6TTMwMCA1NTBoMjk2djY0SDMwMHoiIC8+PC9zdmc+) */
var RefIcon = /*#__PURE__*/React.forwardRef(SwitcherOutlined);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'SwitcherOutlined';
}
var _default = exports.default = RefIcon;