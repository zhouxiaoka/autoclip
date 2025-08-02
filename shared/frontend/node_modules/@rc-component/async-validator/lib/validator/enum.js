"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _rule = _interopRequireDefault(require("../rule"));
var _util = require("../util");
var ENUM = 'enum';
var enumerable = function enumerable(rule, value, callback, source, options) {
  var errors = [];
  var validate = rule.required || !rule.required && source.hasOwnProperty(rule.field);
  if (validate) {
    if ((0, _util.isEmptyValue)(value) && !rule.required) {
      return callback();
    }
    _rule.default.required(rule, value, source, errors, options);
    if (value !== undefined) {
      _rule.default[ENUM](rule, value, source, errors, options);
    }
  }
  callback(errors);
};
var _default = exports.default = enumerable;