"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _DragOutlined = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/DragOutlined"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var DragOutlined = function DragOutlined(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _DragOutlined.default
  }));
};

/**![drag](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjY0IDY0IDg5NiA4OTYiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTkwOS4zIDUwNi4zTDc4MS43IDQwNS42YTcuMjMgNy4yMyAwIDAwLTExLjcgNS43VjQ3Nkg1NDhWMjU0aDY0LjhjNiAwIDkuNC03IDUuNy0xMS43TDUxNy43IDExNC43YTcuMTQgNy4xNCAwIDAwLTExLjMgMEw0MDUuNiAyNDIuM2E3LjIzIDcuMjMgMCAwMDUuNyAxMS43SDQ3NnYyMjJIMjU0di02NC44YzAtNi03LTkuNC0xMS43LTUuN0wxMTQuNyA1MDYuM2E3LjE0IDcuMTQgMCAwMDAgMTEuM2wxMjcuNSAxMDAuOGM0LjcgMy43IDExLjcuNCAxMS43LTUuN1Y1NDhoMjIydjIyMmgtNjQuOGMtNiAwLTkuNCA3LTUuNyAxMS43bDEwMC44IDEyNy41YzIuOSAzLjcgOC41IDMuNyAxMS4zIDBsMTAwLjgtMTI3LjVjMy43LTQuNy40LTExLjctNS43LTExLjdINTQ4VjU0OGgyMjJ2NjQuOGMwIDYgNyA5LjQgMTEuNyA1LjdsMTI3LjUtMTAwLjhhNy4zIDcuMyAwIDAwLjEtMTEuNHoiIC8+PC9zdmc+) */
var RefIcon = /*#__PURE__*/React.forwardRef(DragOutlined);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'DragOutlined';
}
var _default = exports.default = RefIcon;