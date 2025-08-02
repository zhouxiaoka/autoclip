"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'da_DK',
  today: 'I dag',
  now: 'Nu',
  backToToday: 'Gå til i dag',
  ok: 'OK',
  clear: 'Ryd',
  week: 'Uge',
  month: 'Måned',
  year: 'År',
  timeSelect: 'Vælg tidspunkt',
  dateSelect: 'Vælg dato',
  monthSelect: 'Vælg måned',
  yearSelect: 'Vælg år',
  decadeSelect: 'Vælg årti',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'Forrige måned (Page Up)',
  nextMonth: 'Næste måned (Page Down)',
  previousYear: 'Forrige år (Ctrl-venstre pil)',
  nextYear: 'Næste år (Ctrl-højre pil)',
  previousDecade: 'Forrige årti',
  nextDecade: 'Næste årti',
  previousCentury: 'Forrige århundrede',
  nextCentury: 'Næste århundrede'
});
var _default = exports.default = locale;