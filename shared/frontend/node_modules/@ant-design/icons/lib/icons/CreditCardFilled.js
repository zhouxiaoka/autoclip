"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _CreditCardFilled = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/CreditCardFilled"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var CreditCardFilled = function CreditCardFilled(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _CreditCardFilled.default
  }));
};

/**![credit-card](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjY0IDY0IDg5NiA4OTYiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTkyOCAxNjBIOTZjLTE3LjcgMC0zMiAxNC4zLTMyIDMydjE2MGg4OTZWMTkyYzAtMTcuNy0xNC4zLTMyLTMyLTMyek02NCA4MzJjMCAxNy43IDE0LjMgMzIgMzIgMzJoODMyYzE3LjcgMCAzMi0xNC4zIDMyLTMyVjQ0MEg2NHYzOTJ6bTU3OS0xODRjMC00LjQgMy42LTggOC04aDE2NWM0LjQgMCA4IDMuNiA4IDh2NzJjMCA0LjQtMy42IDgtOCA4SDY1MWMtNC40IDAtOC0zLjYtOC04di03MnoiIC8+PC9zdmc+) */
var RefIcon = /*#__PURE__*/React.forwardRef(CreditCardFilled);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'CreditCardFilled';
}
var _default = exports.default = RefIcon;