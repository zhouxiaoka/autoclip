"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _cssinjs = require("@ant-design/cssinjs");
var _index = _interopRequireDefault(require("./index"));
const defaultTheme = (0, _cssinjs.createTheme)(_index.default);
var _default = exports.default = defaultTheme;