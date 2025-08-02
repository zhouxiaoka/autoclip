"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _rule = _interopRequireDefault(require("../rule"));
var _util = require("../util");
var date = function date(rule, value, callback, source, options) {
  // console.log('integer rule called %j', rule);
  var errors = [];
  var validate = rule.required || !rule.required && source.hasOwnProperty(rule.field);
  // console.log('validate on %s value', value);
  if (validate) {
    if ((0, _util.isEmptyValue)(value, 'date') && !rule.required) {
      return callback();
    }
    _rule.default.required(rule, value, source, errors, options);
    if (!(0, _util.isEmptyValue)(value, 'date')) {
      var dateObject;
      if (value instanceof Date) {
        dateObject = value;
      } else {
        dateObject = new Date(value);
      }
      _rule.default.type(rule, dateObject, source, errors, options);
      if (dateObject) {
        _rule.default.range(rule, dateObject.getTime(), source, errors, options);
      }
    }
  }
  callback(errors);
};
var _default = exports.default = date;