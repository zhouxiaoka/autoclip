"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.defaultConfig = exports.DesignTokenContext = void 0;
Object.defineProperty(exports, "defaultTheme", {
  enumerable: true,
  get: function () {
    return _theme.default;
  }
});
var _react = _interopRequireDefault(require("react"));
var _seed = _interopRequireDefault(require("./themes/seed"));
var _theme = _interopRequireDefault(require("./themes/default/theme"));
// ================================ Context =================================
// To ensure snapshot stable. We disable hashed in test env.
const defaultConfig = exports.defaultConfig = {
  token: _seed.default,
  override: {
    override: _seed.default
  },
  hashed: true
};
const DesignTokenContext = exports.DesignTokenContext = /*#__PURE__*/_react.default.createContext(defaultConfig);