"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _StepForwardFilled = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/StepForwardFilled"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var StepForwardFilled = function StepForwardFilled(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _StepForwardFilled.default
  }));
};

/**![step-forward](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjAgMCAxMDI0IDEwMjQiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTY3Ni40IDUyOC45NUwyOTMuMiA4MjkuOTdjLTE0LjI1IDExLjItMzUuMiAxLjEtMzUuMi0xNi45NVYyMTAuOTdjMC0xOC4wNSAyMC45NS0yOC4xNCAzNS4yLTE2Ljk0bDM4My4yIDMwMS4wMmEyMS41MyAyMS41MyAwIDAxMCAzMy45TTY5NCA4NjRoNjRhOCA4IDAgMDA4LThWMTY4YTggOCAwIDAwLTgtOGgtNjRhOCA4IDAgMDAtOCA4djY4OGE4IDggMCAwMDggOCIgLz48L3N2Zz4=) */
var RefIcon = /*#__PURE__*/React.forwardRef(StepForwardFilled);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'StepForwardFilled';
}
var _default = exports.default = RefIcon;