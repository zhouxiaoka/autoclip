"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'tk_TK',
  today: 'Şugün',
  now: 'Şuwagt',
  backToToday: 'Şugüne gaýt',
  ok: 'Bolýar',
  clear: 'Arassala',
  month: 'Aý',
  week: 'Hepde',
  year: 'Ýyl',
  timeSelect: 'Wagt saýla',
  dateSelect: 'Gün saýla',
  monthSelect: 'Aý saýla',
  yearSelect: 'Ýyl saýla',
  decadeSelect: 'On ýyllygy saýla',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'Öňki aý (PageUp)',
  nextMonth: 'Soňky aý (PageDown)',
  previousYear: 'Öňki ýyl (Control + çep)',
  nextYear: 'Soňky ýyl (Control + sag)',
  previousDecade: 'Öňki on ýyl',
  nextDecade: 'Soňky on ýyl',
  previousCentury: 'Öňki asyr',
  nextCentury: 'Soňky asyr'
});
var _default = exports.default = locale;