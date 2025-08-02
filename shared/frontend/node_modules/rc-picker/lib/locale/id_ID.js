"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'id_ID',
  today: 'Hari ini',
  now: 'Sekarang',
  backToToday: 'Kembali ke hari ini',
  ok: 'Baik',
  clear: 'Bersih',
  week: 'Minggu',
  month: 'Bulan',
  year: 'Tahun',
  timeSelect: 'pilih waktu',
  dateSelect: 'pilih tanggal',
  weekSelect: 'Pilih satu minggu',
  monthSelect: 'Pilih satu bulan',
  yearSelect: 'Pilih satu tahun',
  decadeSelect: 'Pilih satu dekade',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'Bulan sebelumnya (PageUp)',
  nextMonth: 'Bulan selanjutnya (PageDown)',
  previousYear: 'Tahun lalu (Control + kiri)',
  nextYear: 'Tahun selanjutnya (Kontrol + kanan)',
  previousDecade: 'Dekade terakhir',
  nextDecade: 'Dekade berikutnya',
  previousCentury: 'Abad terakhir',
  nextCentury: 'Abad berikutnya'
});
var _default = exports.default = locale;