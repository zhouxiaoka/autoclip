"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _NotificationFilled = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/NotificationFilled"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var NotificationFilled = function NotificationFilled(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _NotificationFilled.default
  }));
};

/**![notification](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjY0IDY0IDg5NiA4OTYiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTg4MCAxMTJjLTMuOCAwLTcuNy43LTExLjYgMi4zTDI5MiAzNDUuOUgxMjhjLTguOCAwLTE2IDcuNC0xNiAxNi42djI5OWMwIDkuMiA3LjIgMTYuNiAxNiAxNi42aDEwMS42Yy0zLjcgMTEuNi01LjYgMjMuOS01LjYgMzYuNCAwIDY1LjkgNTMuOCAxMTkuNSAxMjAgMTE5LjUgNTUuNCAwIDEwMi4xLTM3LjYgMTE1LjktODguNGw0MDguNiAxNjQuMmMzLjkgMS41IDcuOCAyLjMgMTEuNiAyLjMgMTYuOSAwIDMyLTE0LjIgMzItMzMuMlYxNDUuMkM5MTIgMTI2LjIgODk3IDExMiA4ODAgMTEyek0zNDQgNzYyLjNjLTI2LjUgMC00OC0yMS40LTQ4LTQ3LjggMC0xMS4yIDMuOS0yMS45IDExLTMwLjRsODQuOSAzNC4xYy0yIDI0LjYtMjIuNyA0NC4xLTQ3LjkgNDQuMXoiIC8+PC9zdmc+) */
var RefIcon = /*#__PURE__*/React.forwardRef(NotificationFilled);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'NotificationFilled';
}
var _default = exports.default = RefIcon;