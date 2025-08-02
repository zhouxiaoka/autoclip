"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'nb_NO',
  today: 'I dag',
  now: 'Nå',
  backToToday: 'Gå til i dag',
  ok: 'OK',
  clear: 'Annuller',
  week: 'Uke',
  month: 'Måned',
  year: 'År',
  timeSelect: 'Velg tidspunkt',
  dateSelect: 'Velg dato',
  weekSelect: 'Velg uke',
  monthSelect: 'Velg måned',
  yearSelect: 'Velg år',
  decadeSelect: 'Velg tiår',
  dateFormat: 'DD.MM.YYYY',
  dayFormat: 'DD',
  dateTimeFormat: 'DD.MM.YYYY HH:mm:ss',
  previousMonth: 'Forrige måned (PageUp)',
  nextMonth: 'Neste måned (PageDown)',
  previousYear: 'Forrige år (Control + venstre)',
  nextYear: 'Neste år (Control + høyre)',
  previousDecade: 'Forrige tiår',
  nextDecade: 'Neste tiår',
  previousCentury: 'Forrige århundre',
  nextCentury: 'Neste århundre'
});
var _default = exports.default = locale;