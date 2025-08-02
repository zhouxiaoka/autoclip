"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _TrophyFilled = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/TrophyFilled"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var TrophyFilled = function TrophyFilled(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _TrophyFilled.default
  }));
};

/**![trophy](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjY0IDY0IDg5NiA4OTYiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTg2OCAxNjBoLTkydi00MGMwLTQuNC0zLjYtOC04LThIMjU2Yy00LjQgMC04IDMuNi04IDh2NDBoLTkyYTQ0IDQ0IDAgMDAtNDQgNDR2MTQ4YzAgODEuNyA2MCAxNDkuNiAxMzguMiAxNjJDMjY1LjYgNjMwLjIgMzU5IDcyMS44IDQ3NiA3MzQuNXYxMDUuMkgyODBjLTE3LjcgMC0zMiAxNC4zLTMyIDMyVjkwNGMwIDQuNCAzLjYgOCA4IDhoNTEyYzQuNCAwIDgtMy42IDgtOHYtMzIuM2MwLTE3LjctMTQuMy0zMi0zMi0zMkg1NDhWNzM0LjVDNjY1IDcyMS44IDc1OC40IDYzMC4yIDc3My44IDUxNCA4NTIgNTAxLjYgOTEyIDQzMy43IDkxMiAzNTJWMjA0YTQ0IDQ0IDAgMDAtNDQtNDR6TTI0OCA0MzkuNmMtMzcuMS0xMS45LTY0LTQ2LjctNjQtODcuNlYyMzJoNjR2MjA3LjZ6TTg0MCAzNTJjMCA0MS0yNi45IDc1LjgtNjQgODcuNlYyMzJoNjR2MTIweiIgLz48L3N2Zz4=) */
var RefIcon = /*#__PURE__*/React.forwardRef(TrophyFilled);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'TrophyFilled';
}
var _default = exports.default = RefIcon;