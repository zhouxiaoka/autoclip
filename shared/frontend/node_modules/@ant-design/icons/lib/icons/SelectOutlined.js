"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _SelectOutlined = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/SelectOutlined"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var SelectOutlined = function SelectOutlined(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _SelectOutlined.default
  }));
};

/**![select](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjY0IDY0IDg5NiA4OTYiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTg4MCAxMTJIMTQ0Yy0xNy43IDAtMzIgMTQuMy0zMiAzMnY3MzZjMCAxNy43IDE0LjMgMzIgMzIgMzJoMzYwYzQuNCAwIDgtMy42IDgtOHYtNTZjMC00LjQtMy42LTgtOC04SDE4NFYxODRoNjU2djMyMGMwIDQuNCAzLjYgOCA4IDhoNTZjNC40IDAgOC0zLjYgOC04VjE0NGMwLTE3LjctMTQuMy0zMi0zMi0zMnpNNjUzLjMgNTk5LjRsNTIuMi01Mi4yYTguMDEgOC4wMSAwIDAwLTQuNy0xMy42bC0xNzkuNC0yMWMtNS4xLS42LTkuNSAzLjctOC45IDguOWwyMSAxNzkuNGMuOCA2LjYgOC45IDkuNCAxMy42IDQuN2w1Mi40LTUyLjQgMjU2LjIgMjU2LjJjMy4xIDMuMSA4LjIgMy4xIDExLjMgMGw0Mi40LTQyLjRjMy4xLTMuMSAzLjEtOC4yIDAtMTEuM0w2NTMuMyA1OTkuNHoiIC8+PC9zdmc+) */
var RefIcon = /*#__PURE__*/React.forwardRef(SelectOutlined);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'SelectOutlined';
}
var _default = exports.default = RefIcon;