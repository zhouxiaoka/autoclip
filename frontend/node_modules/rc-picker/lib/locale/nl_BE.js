"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'nl_BE',
  today: 'Vandaag',
  now: 'Nu',
  backToToday: 'Terug naar vandaag',
  ok: 'OK',
  clear: 'Reset',
  week: 'Week',
  month: 'Maand',
  year: 'Jaar',
  timeSelect: 'Selecteer tijd',
  dateSelect: 'Selecteer datum',
  monthSelect: 'Kies een maand',
  yearSelect: 'Kies een jaar',
  decadeSelect: 'Kies een decennium',
  dateFormat: 'D-M-YYYY',
  dateTimeFormat: 'D-M-YYYY HH:mm:ss',
  previousMonth: 'Vorige maand (PageUp)',
  nextMonth: 'Volgende maand (PageDown)',
  previousYear: 'Vorig jaar (Control + left)',
  nextYear: 'Volgend jaar (Control + right)',
  previousDecade: 'Vorig decennium',
  nextDecade: 'Volgend decennium',
  previousCentury: 'Vorige eeuw',
  nextCentury: 'Volgende eeuw'
});
var _default = exports.default = locale;