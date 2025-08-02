"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _CalendarFilled = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/CalendarFilled"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var CalendarFilled = function CalendarFilled(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _CalendarFilled.default
  }));
};

/**![calendar](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjY0IDY0IDg5NiA4OTYiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTExMiA4ODBjMCAxNy43IDE0LjMgMzIgMzIgMzJoNzM2YzE3LjcgMCAzMi0xNC4zIDMyLTMyVjQ2MEgxMTJ2NDIwem03NjgtNjk2SDcxMnYtNjRjMC00LjQtMy42LTgtOC04aC01NmMtNC40IDAtOCAzLjYtOCA4djY0SDM4NHYtNjRjMC00LjQtMy42LTgtOC04aC01NmMtNC40IDAtOCAzLjYtOCA4djY0SDE0NGMtMTcuNyAwLTMyIDE0LjMtMzIgMzJ2MTc2aDgwMFYyMTZjMC0xNy43LTE0LjMtMzItMzItMzJ6IiAvPjwvc3ZnPg==) */
var RefIcon = /*#__PURE__*/React.forwardRef(CalendarFilled);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'CalendarFilled';
}
var _default = exports.default = RefIcon;