"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireDefault(require("react"));
var _context = _interopRequireDefault(require("./context"));
const useApp = () => _react.default.useContext(_context.default);
var _default = exports.default = useApp;