"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _RollbackOutlined = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/RollbackOutlined"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var RollbackOutlined = function RollbackOutlined(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _RollbackOutlined.default
  }));
};

/**![rollback](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjY0IDY0IDg5NiA4OTYiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTc5MyAyNDJIMzY2di03NGMwLTYuNy03LjctMTAuNC0xMi45LTYuM2wtMTQyIDExMmE4IDggMCAwMDAgMTIuNmwxNDIgMTEyYzUuMiA0LjEgMTIuOS40IDEyLjktNi4zdi03NGg0MTV2NDcwSDE3NWMtNC40IDAtOCAzLjYtOCA4djYwYzAgNC40IDMuNiA4IDggOGg2MThjMzUuMyAwIDY0LTI4LjcgNjQtNjRWMzA2YzAtMzUuMy0yOC43LTY0LTY0LTY0eiIgLz48L3N2Zz4=) */
var RefIcon = /*#__PURE__*/React.forwardRef(RollbackOutlined);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'RollbackOutlined';
}
var _default = exports.default = RefIcon;