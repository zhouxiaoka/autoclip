"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _Panel = _interopRequireDefault(require("./Panel"));
var _Splitter = _interopRequireDefault(require("./Splitter"));
const Splitter = _Splitter.default;
Splitter.Panel = _Panel.default;
var _default = exports.default = Splitter;