"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _Group = _interopRequireDefault(require("./Group"));
var _Input = _interopRequireDefault(require("./Input"));
var _OTP = _interopRequireDefault(require("./OTP"));
var _Password = _interopRequireDefault(require("./Password"));
var _Search = _interopRequireDefault(require("./Search"));
var _TextArea = _interopRequireDefault(require("./TextArea"));
const Input = _Input.default;
Input.Group = _Group.default;
Input.Search = _Search.default;
Input.TextArea = _TextArea.default;
Input.Password = _Password.default;
Input.OTP = _OTP.default;
var _default = exports.default = Input;