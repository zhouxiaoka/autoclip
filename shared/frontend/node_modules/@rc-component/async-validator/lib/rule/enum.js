"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _util = require("../util");
var ENUM = 'enum';
var enumerable = function enumerable(rule, value, source, errors, options) {
  rule[ENUM] = Array.isArray(rule[ENUM]) ? rule[ENUM] : [];
  if (rule[ENUM].indexOf(value) === -1) {
    errors.push((0, _util.format)(options.messages[ENUM], rule.fullField, rule[ENUM].join(', ')));
  }
};
var _default = exports.default = enumerable;