"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _rule = _interopRequireDefault(require("../rule"));
var _util = require("../util");
var string = function string(rule, value, callback, source, options) {
  var errors = [];
  var validate = rule.required || !rule.required && source.hasOwnProperty(rule.field);
  if (validate) {
    if ((0, _util.isEmptyValue)(value, 'string') && !rule.required) {
      return callback();
    }
    _rule.default.required(rule, value, source, errors, options, 'string');
    if (!(0, _util.isEmptyValue)(value, 'string')) {
      _rule.default.type(rule, value, source, errors, options);
      _rule.default.range(rule, value, source, errors, options);
      _rule.default.pattern(rule, value, source, errors, options);
      if (rule.whitespace === true) {
        _rule.default.whitespace(rule, value, source, errors, options);
      }
    }
  }
  callback(errors);
};
var _default = exports.default = string;