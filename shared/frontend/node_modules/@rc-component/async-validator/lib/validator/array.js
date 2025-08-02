"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _index = _interopRequireDefault(require("../rule/index"));
var array = function array(rule, value, callback, source, options) {
  var errors = [];
  var validate = rule.required || !rule.required && source.hasOwnProperty(rule.field);
  if (validate) {
    if ((value === undefined || value === null) && !rule.required) {
      return callback();
    }
    _index.default.required(rule, value, source, errors, options, 'array');
    if (value !== undefined && value !== null) {
      _index.default.type(rule, value, source, errors, options);
      _index.default.range(rule, value, source, errors, options);
    }
  }
  callback(errors);
};
var _default = exports.default = array;