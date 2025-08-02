"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var React = _interopRequireWildcard(require("react"));
var _TwitchOutlined = _interopRequireDefault(require("@ant-design/icons-svg/lib/asn/TwitchOutlined"));
var _AntdIcon = _interopRequireDefault(require("../components/AntdIcon"));
// GENERATE BY ./scripts/generate.ts
// DON NOT EDIT IT MANUALLY

var TwitchOutlined = function TwitchOutlined(props, ref) {
  return /*#__PURE__*/React.createElement(_AntdIcon.default, (0, _extends2.default)({}, props, {
    ref: ref,
    icon: _TwitchOutlined.default
  }));
};

/**![twitch](data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIGZpbGw9IiNjYWNhY2EiIGZpbGwtcnVsZT0iZXZlbm9kZCIgdmlld0JveD0iNjQgNjQgODk2IDg5NiIgZm9jdXNhYmxlPSJmYWxzZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMTY2LjEzIDExMkwxMTQgMjUxLjE3djU1Ni40NmgxOTEuMlY5MTJoMTA0LjRsMTA0LjIzLTEwNC40aDE1Ni41TDg3OSA1OTlWMTEyem02OS41NCA2OS41SDgwOS41djM4Mi42M0w2ODcuNzcgNjg1Ljg3SDQ5Ni41TDM5Mi4yNyA3OTAuMVY2ODUuODdoLTE1Ni42ek00MjcgNTI5LjRoNjkuNVYzMjAuNzNINDI3em0xOTEuMTcgMGg2OS41M1YzMjAuNzNoLTY5LjUzeiIgLz48L3N2Zz4=) */
var RefIcon = /*#__PURE__*/React.forwardRef(TwitchOutlined);
if (process.env.NODE_ENV !== 'production') {
  RefIcon.displayName = 'TwitchOutlined';
}
var _default = exports.default = RefIcon;