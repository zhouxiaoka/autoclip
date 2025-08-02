"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'ca_ES',
  today: 'Avui',
  now: 'Ara',
  backToToday: 'Tornar a avui',
  ok: 'Acceptar',
  clear: 'Netejar',
  week: 'Setmana',
  month: 'Mes',
  year: 'Any',
  timeSelect: 'Seleccionar hora',
  dateSelect: 'Seleccionar data',
  monthSelect: 'Escollir un mes',
  yearSelect: 'Escollir un any',
  decadeSelect: 'Escollir una dècada',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'Mes anterior (PageUp)',
  nextMonth: 'Mes següent (PageDown)',
  previousYear: 'Any anterior (Control + left)',
  nextYear: 'Mes següent (Control + right)',
  previousDecade: 'Dècada anterior',
  nextDecade: 'Dècada següent',
  previousCentury: 'Segle anterior',
  nextCentury: 'Segle següent'
});
var _default = exports.default = locale;