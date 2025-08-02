"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'et_EE',
  today: 'Täna',
  now: 'Praegu',
  backToToday: 'Tagasi tänase juurde',
  ok: 'OK',
  clear: 'Tühista',
  week: 'Nädal',
  month: 'Kuu',
  year: 'Aasta',
  timeSelect: 'Vali aeg',
  dateSelect: 'Vali kuupäev',
  monthSelect: 'Vali kuu',
  yearSelect: 'Vali aasta',
  decadeSelect: 'Vali dekaad',
  dateFormat: 'D.M.YYYY',
  dateTimeFormat: 'D.M.YYYY HH:mm:ss',
  previousMonth: 'Eelmine kuu (PageUp)',
  nextMonth: 'Järgmine kuu (PageDown)',
  previousYear: 'Eelmine aasta (Control + left)',
  nextYear: 'Järgmine aasta (Control + right)',
  previousDecade: 'Eelmine dekaad',
  nextDecade: 'Järgmine dekaad',
  previousCentury: 'Eelmine sajand',
  nextCentury: 'Järgmine sajand'
});
var _default = exports.default = locale;