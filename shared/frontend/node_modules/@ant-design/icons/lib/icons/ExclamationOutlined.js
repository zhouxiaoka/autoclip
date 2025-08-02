"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _ExclamationOutlined = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/ExclamationOutlined"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var ExclamationOutlined = function ExclamationOutlined(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _ExclamationOutlined.default
  }));
};

/**![exclamation](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjY0IDY0IDg5NiA4OTYiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTQ0OCA4MDRhNjQgNjQgMCAxMDEyOCAwIDY0IDY0IDAgMTAtMTI4IDB6bTMyLTE2OGg2NGM0LjQgMCA4LTMuNiA4LThWMTY0YzAtNC40LTMuNi04LTgtOGgtNjRjLTQuNCAwLTggMy42LTggOHY0NjRjMCA0LjQgMy42IDggOCA4eiIgLz48L3N2Zz4=) */
var RefIcon = /*#__PURE__*/React.forwardRef(ExclamationOutlined);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'ExclamationOutlined';
}
var _default = exports.default = RefIcon;