"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _CSSCalculator = _interopRequireDefault(require("./CSSCalculator"));
var _NumCalculator = _interopRequireDefault(require("./NumCalculator"));
var genCalc = function genCalc(type, unitlessCssVar) {
  var Calculator = type === 'css' ? _CSSCalculator.default : _NumCalculator.default;
  return function (num) {
    return new Calculator(num, unitlessCssVar);
  };
};
var _default = exports.default = genCalc;