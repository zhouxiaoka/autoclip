"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _SwitcherFilled = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/SwitcherFilled"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var SwitcherFilled = function SwitcherFilled(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _SwitcherFilled.default
  }));
};

/**![switcher](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjY0IDY0IDg5NiA4OTYiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTc1MiAyNDBIMTQ0Yy0xNy43IDAtMzIgMTQuMy0zMiAzMnY2MDhjMCAxNy43IDE0LjMgMzIgMzIgMzJoNjA4YzE3LjcgMCAzMi0xNC4zIDMyLTMyVjI3MmMwLTE3LjctMTQuMy0zMi0zMi0zMnpNNTk2IDYwNmMwIDQuNC0zLjYgOC04IDhIMzA4Yy00LjQgMC04LTMuNi04LTh2LTQ4YzAtNC40IDMuNi04IDgtOGgyODBjNC40IDAgOCAzLjYgOCA4djQ4em0yODQtNDk0SDI2NGMtNC40IDAtOCAzLjYtOCA4djU2YzAgNC40IDMuNiA4IDggOGg1NzZ2NTc2YzAgNC40IDMuNiA4IDggOGg1NmM0LjQgMCA4LTMuNiA4LThWMTQ0YzAtMTcuNy0xNC4zLTMyLTMyLTMyeiIgLz48L3N2Zz4=) */
var RefIcon = /*#__PURE__*/React.forwardRef(SwitcherFilled);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'SwitcherFilled';
}
var _default = exports.default = RefIcon;