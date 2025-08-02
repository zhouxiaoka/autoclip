"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _PauseOutlined = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/PauseOutlined"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var PauseOutlined = function PauseOutlined(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _PauseOutlined.default
  }));
};

/**![pause](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjY0IDY0IDg5NiA4OTYiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTMwNCAxNzZoODB2NjcyaC04MHptNDA4IDBoLTY0Yy00LjQgMC04IDMuNi04IDh2NjU2YzAgNC40IDMuNiA4IDggOGg2NGM0LjQgMCA4LTMuNiA4LThWMTg0YzAtNC40LTMuNi04LTgtOHoiIC8+PC9zdmc+) */
var RefIcon = /*#__PURE__*/React.forwardRef(PauseOutlined);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'PauseOutlined';
}
var _default = exports.default = RefIcon;