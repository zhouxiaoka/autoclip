"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _util = require("../util");
var required = function required(rule, value, source, errors, options, type) {
  if (rule.required && (!source.hasOwnProperty(rule.field) || (0, _util.isEmptyValue)(value, type || rule.type))) {
    errors.push((0, _util.format)(options.messages.required, rule.fullField));
  }
};
var _default = exports.default = required;