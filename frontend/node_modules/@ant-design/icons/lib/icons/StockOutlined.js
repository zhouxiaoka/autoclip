"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _StockOutlined = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/StockOutlined"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var StockOutlined = function StockOutlined(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _StockOutlined.default
  }));
};

/**![stock](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjY0IDY0IDg5NiA4OTYiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTkwNCA3NDdIMTIwYy00LjQgMC04IDMuNi04IDh2NTZjMCA0LjQgMy42IDggOCA4aDc4NGM0LjQgMCA4LTMuNiA4LTh2LTU2YzAtNC40LTMuNi04LTgtOHpNMTY1LjcgNjIxLjhsMzkuNyAzOS41YzMuMSAzLjEgOC4yIDMuMSAxMS4zIDBsMjM0LjctMjMzLjkgOTcuNiA5Ny4zYTMyLjExIDMyLjExIDAgMDA0NS4yIDBsMjY0LjItMjYzLjJjMy4xLTMuMSAzLjEtOC4yIDAtMTEuM2wtMzkuNy0zOS42YTguMDMgOC4wMyAwIDAwLTExLjMgMGwtMjM1LjcgMjM1LTk3LjctOTcuM2EzMi4xMSAzMi4xMSAwIDAwLTQ1LjIgMEwxNjUuNyA2MTAuNWE3Ljk0IDcuOTQgMCAwMDAgMTEuM3oiIC8+PC9zdmc+) */
var RefIcon = /*#__PURE__*/React.forwardRef(StockOutlined);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'StockOutlined';
}
var _default = exports.default = RefIcon;