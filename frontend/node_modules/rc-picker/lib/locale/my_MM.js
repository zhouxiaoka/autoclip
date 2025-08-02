"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'my_MM',
  today: 'ယနေ့',
  now: 'ယခု',
  backToToday: 'ယနေ့မတိုင်ခင်သို့',
  ok: 'OK',
  clear: 'ရှင်းမည်',
  week: 'အပတ်',
  month: 'လ',
  year: 'နှစ်',
  timeSelect: 'အချိန်ကိုရွေး',
  dateSelect: 'နေ့ကိုရွေး',
  weekSelect: 'သီတင်းပတ်ကိုရွေး',
  monthSelect: 'လကိုရွေး',
  yearSelect: 'နှစ်ကိုရွေး',
  decadeSelect: 'ဆယ်စုနှစ်ကိုရွေး',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousMonth: 'ယခင်လ (PageUp)',
  nextMonth: 'နောက်လ (PageDown)',
  previousYear: 'ယခင်နှစ် (Control + left)',
  nextYear: 'နောက်နှစ် (Control + right)',
  previousDecade: 'ယခင်ဆယ်စုနှစ်',
  nextDecade: 'နောက်ဆယ်စုနှစ်',
  previousCentury: 'ယခင်ရာစုနှစ်',
  nextCentury: 'နောက်ရာစုနှစ်'
});
var _default = exports.default = locale;