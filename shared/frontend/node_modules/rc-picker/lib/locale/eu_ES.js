"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'eu_ES',
  today: 'Gaur',
  now: 'Orain',
  backToToday: 'Gaur itzuli',
  ok: 'OK',
  clear: 'Garbitu',
  week: 'Asteko',
  month: 'Hilabete',
  year: 'Urte',
  timeSelect: 'Ordua aukeratu',
  dateSelect: 'Eguna aukeratu',
  weekSelect: 'Astea aukeratu',
  monthSelect: 'Hilabetea aukeratu',
  yearSelect: 'Urtea aukeratu',
  decadeSelect: 'Hamarkada aukeratu',
  dateFormat: 'YYYY/M/D',
  dateTimeFormat: 'YYYY/M/D HH:mm:ss',
  monthBeforeYear: false,
  previousMonth: 'Aurreko hilabetea (RePag)',
  nextMonth: 'Urrengo hilabetea (AvPag)',
  previousYear: 'Aurreko urtea (Control + ezkerra)',
  nextYear: 'Urrento urtea (Control + eskuina)',
  previousDecade: 'Aurreko hamarkada',
  nextDecade: 'Urrengo hamarkada',
  previousCentury: 'Aurreko mendea',
  nextCentury: 'Urrengo mendea'
});
var _default = exports.default = locale;