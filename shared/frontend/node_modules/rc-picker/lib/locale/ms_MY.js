"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'ms_MY',
  today: 'Hari ini',
  now: 'Sekarang',
  backToToday: 'Kembali ke hari ini',
  ok: 'OK',
  timeSelect: 'Pilih masa',
  dateSelect: 'Pilih tarikh',
  weekSelect: 'Pilih minggu',
  clear: 'Padam',
  week: 'Minggu',
  month: 'Bulan',
  year: 'Tahun',
  previousMonth: 'Bulan lepas',
  nextMonth: 'Bulan depan',
  monthSelect: 'Pilih bulan',
  yearSelect: 'Pilih tahun',
  decadeSelect: 'Pilih dekad',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousYear: 'Tahun lepas (Ctrl+left)',
  nextYear: 'Tahun depan (Ctrl+right)',
  previousDecade: 'Dekad lepas',
  nextDecade: 'Dekad depan',
  previousCentury: 'Abad lepas',
  nextCentury: 'Abad depan',
  monthBeforeYear: false
});
var _default = exports.default = locale;