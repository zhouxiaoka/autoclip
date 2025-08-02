"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _App = _interopRequireDefault(require("./App"));
var _useApp = _interopRequireDefault(require("./useApp"));
const App = _App.default;
App.useApp = _useApp.default;
var _default = exports.default = App;