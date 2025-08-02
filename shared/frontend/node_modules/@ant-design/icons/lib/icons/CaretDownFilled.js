"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _CaretDownFilled = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/CaretDownFilled"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var CaretDownFilled = function CaretDownFilled(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _CaretDownFilled.default
  }));
};

/**![caret-down](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjAgMCAxMDI0IDEwMjQiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTg0MC40IDMwMEgxODMuNmMtMTkuNyAwLTMwLjcgMjAuOC0xOC41IDM1bDMyOC40IDM4MC44YzkuNCAxMC45IDI3LjUgMTAuOSAzNyAwTDg1OC45IDMzNWMxMi4yLTE0LjIgMS4yLTM1LTE4LjUtMzV6IiAvPjwvc3ZnPg==) */
var RefIcon = /*#__PURE__*/React.forwardRef(CaretDownFilled);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'CaretDownFilled';
}
var _default = exports.default = RefIcon;