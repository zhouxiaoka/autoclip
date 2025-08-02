"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
Object.defineProperty(exports, "genCalc", {
  enumerable: true,
  get: function get() {
    return _calc.default;
  }
});
Object.defineProperty(exports, "genStyleUtils", {
  enumerable: true,
  get: function get() {
    return _genStyleUtils.default;
  }
});
Object.defineProperty(exports, "mergeToken", {
  enumerable: true,
  get: function get() {
    return _statistic.merge;
  }
});
Object.defineProperty(exports, "statistic", {
  enumerable: true,
  get: function get() {
    return _statistic.statistic;
  }
});
Object.defineProperty(exports, "statisticToken", {
  enumerable: true,
  get: function get() {
    return _statistic.default;
  }
});
var _genStyleUtils = _interopRequireDefault(require("./util/genStyleUtils"));
var _calc = _interopRequireDefault(require("./util/calc"));
var _statistic = _interopRequireWildcard(require("./util/statistic"));