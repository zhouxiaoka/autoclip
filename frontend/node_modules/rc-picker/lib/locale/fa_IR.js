"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'fa_IR',
  today: 'امروز',
  now: 'اکنون',
  backToToday: 'بازگشت به روز',
  ok: 'باشه',
  clear: 'پاک کردن',
  week: 'هفته',
  month: 'ماه',
  year: 'سال',
  timeSelect: 'انتخاب زمان',
  dateSelect: 'انتخاب تاریخ',
  monthSelect: 'یک ماه را انتخاب کنید',
  yearSelect: 'یک سال را انتخاب کنید',
  decadeSelect: 'یک دهه را انتخاب کنید',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousMonth: 'ماه قبل (PageUp)',
  nextMonth: 'ماه بعد (PageDown)',
  previousYear: 'سال قبل (Control + left)',
  nextYear: 'سال بعد (Control + right)',
  previousDecade: 'دهه قبل',
  nextDecade: 'دهه بعد',
  previousCentury: 'قرن قبل',
  nextCentury: 'قرن بعد'
});
var _default = exports.default = locale;