"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _CompassFilled = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/CompassFilled"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var CompassFilled = function CompassFilled(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _CompassFilled.default
  }));
};

/**![compass](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIHZpZXdCb3g9IjY0IDY0IDg5NiA4OTYiIGZvY3VzYWJsZT0iZmFsc2UiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTUxMiA2NEMyNjQuNiA2NCA2NCAyNjQuNiA2NCA1MTJzMjAwLjYgNDQ4IDQ0OCA0NDggNDQ4LTIwMC42IDQ0OC00NDhTNzU5LjQgNjQgNTEyIDY0ek0zMjcuMyA3MDIuNGMtMiAuOS00LjQgMC01LjMtMi4xLS40LTEtLjQtMi4yIDAtMy4ybDk4LjctMjI1LjUgMTMyLjEgMTMyLjEtMjI1LjUgOTguN3ptMzc1LjEtMzc1LjFsLTk4LjcgMjI1LjUtMTMyLjEtMTMyLjFMNjk3LjEgMzIyYzItLjkgNC40IDAgNS4zIDIuMS40IDEgLjQgMi4xIDAgMy4yeiIgLz48L3N2Zz4=) */
var RefIcon = /*#__PURE__*/React.forwardRef(CompassFilled);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'CompassFilled';
}
var _default = exports.default = RefIcon;