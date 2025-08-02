"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'ur_PK',
  today: 'آج',
  now: 'ابھی',
  backToToday: 'آج واپس',
  ok: 'ٹھیک ہے',
  clear: 'صاف',
  week: 'ہفتہ',
  month: 'مہینہ',
  year: 'سال',
  timeSelect: 'وقت منتخب کریں',
  dateSelect: 'تاریخ منتخب کریں',
  weekSelect: 'ایک ہفتہ کا انتخاب کریں',
  monthSelect: 'ایک مہینہ کا انتخاب کریں',
  yearSelect: 'ایک سال کا انتخاب کریں',
  decadeSelect: 'ایک دہائی کا انتخاب کریں',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousMonth: 'پچھلے مہینے (PageUp)',
  nextMonth: 'اگلے مہینے (PageDown)',
  previousYear: 'گزشتہ سال (Control + left)',
  nextYear: 'اگلے سال (Control + right)',
  previousDecade: 'پچھلی دہائی',
  nextDecade: 'اگلی دہائی',
  previousCentury: 'پچھلی صدی',
  nextCentury: 'اگلی صدی'
});
var _default = exports.default = locale;