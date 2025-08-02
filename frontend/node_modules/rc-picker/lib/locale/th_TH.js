"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'th_TH',
  today: 'วันนี้',
  now: 'ตอนนี้',
  backToToday: 'กลับไปยังวันนี้',
  ok: 'ตกลง',
  clear: 'ลบล้าง',
  week: 'สัปดาห์',
  month: 'เดือน',
  year: 'ปี',
  timeSelect: 'เลือกเวลา',
  dateSelect: 'เลือกวัน',
  monthSelect: 'เลือกเดือน',
  yearSelect: 'เลือกปี',
  decadeSelect: 'เลือกทศวรรษ',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'เดือนก่อนหน้า (PageUp)',
  nextMonth: 'เดือนถัดไป (PageDown)',
  previousYear: 'ปีก่อนหน้า (Control + left)',
  nextYear: 'ปีถัดไป (Control + right)',
  previousDecade: 'ทศวรรษก่อนหน้า',
  nextDecade: 'ทศวรรษถัดไป',
  previousCentury: 'ศตวรรษก่อนหน้า',
  nextCentury: 'ศตวรรษถัดไป'
});
var _default = exports.default = locale;