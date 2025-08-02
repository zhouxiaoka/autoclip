"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'tr_TR',
  today: 'Bugün',
  now: 'Şimdi',
  backToToday: 'Bugüne Geri Dön',
  ok: 'Tamam',
  clear: 'Temizle',
  week: 'Hafta',
  month: 'Ay',
  year: 'Yıl',
  timeSelect: 'Zaman Seç',
  dateSelect: 'Tarih Seç',
  monthSelect: 'Ay Seç',
  yearSelect: 'Yıl Seç',
  decadeSelect: 'On Yıl Seç',
  dateFormat: 'DD/MM/YYYY',
  dateTimeFormat: 'DD/MM/YYYY HH:mm:ss',
  previousMonth: 'Önceki Ay (PageUp)',
  nextMonth: 'Sonraki Ay (PageDown)',
  previousYear: 'Önceki Yıl (Control + Sol)',
  nextYear: 'Sonraki Yıl (Control + Sağ)',
  previousDecade: 'Önceki On Yıl',
  nextDecade: 'Sonraki On Yıl',
  previousCentury: 'Önceki Yüzyıl',
  nextCentury: 'Sonraki Yüzyıl',
  shortWeekDays: ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'],
  shortMonths: ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']
});
var _default = exports.default = locale;