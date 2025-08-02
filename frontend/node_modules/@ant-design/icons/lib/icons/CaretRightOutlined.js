"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _CaretRightOutlined = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/CaretRightOutlined"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var CaretRightOutlined = function CaretRightOutlined(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _CaretRightOutlined.default
  }));
};

/**![caret-right](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjAgMCAxMDI0IDEwMjQiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTcxNS44IDQ5My41TDMzNSAxNjUuMWMtMTQuMi0xMi4yLTM1LTEuMi0zNSAxOC41djY1Ni44YzAgMTkuNyAyMC44IDMwLjcgMzUgMTguNWwzODAuOC0zMjguNGMxMC45LTkuNCAxMC45LTI3LjYgMC0zN3oiIC8+PC9zdmc+) */
var RefIcon = /*#__PURE__*/React.forwardRef(CaretRightOutlined);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'CaretRightOutlined';
}
var _default = exports.default = RefIcon;