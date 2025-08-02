"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _any = _interopRequireDefault(require("./any"));
var _array = _interopRequireDefault(require("./array"));
var _boolean = _interopRequireDefault(require("./boolean"));
var _date = _interopRequireDefault(require("./date"));
var _enum = _interopRequireDefault(require("./enum"));
var _float = _interopRequireDefault(require("./float"));
var _integer = _interopRequireDefault(require("./integer"));
var _method = _interopRequireDefault(require("./method"));
var _number = _interopRequireDefault(require("./number"));
var _object = _interopRequireDefault(require("./object"));
var _pattern = _interopRequireDefault(require("./pattern"));
var _regexp = _interopRequireDefault(require("./regexp"));
var _required = _interopRequireDefault(require("./required"));
var _string = _interopRequireDefault(require("./string"));
var _type = _interopRequireDefault(require("./type"));
var _default = exports.default = {
  string: _string.default,
  method: _method.default,
  number: _number.default,
  boolean: _boolean.default,
  regexp: _regexp.default,
  integer: _integer.default,
  float: _float.default,
  array: _array.default,
  object: _object.default,
  enum: _enum.default,
  pattern: _pattern.default,
  date: _date.default,
  url: _type.default,
  hex: _type.default,
  email: _type.default,
  required: _required.default,
  any: _any.default
};