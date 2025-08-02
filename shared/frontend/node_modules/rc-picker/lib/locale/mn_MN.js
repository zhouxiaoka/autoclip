"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'mn_MN',
  today: 'Өнөөдөр',
  now: 'Одоо',
  backToToday: 'Өнөөдөрлүү буцах',
  ok: 'OK',
  clear: 'Цэвэрлэх',
  week: 'Долоо хоног',
  month: 'Сар',
  year: 'Жил',
  timeSelect: 'Цаг сонгох',
  dateSelect: 'Огноо сонгох',
  weekSelect: '7 хоног сонгох',
  monthSelect: 'Сар сонгох',
  yearSelect: 'Жил сонгох',
  decadeSelect: 'Арван сонгох',
  dateFormat: 'YYYY/MM/DD',
  dayFormat: 'DD',
  dateTimeFormat: 'YYYY/MM/DD HH:mm:ss',
  previousMonth: 'Өмнөх сар (PageUp)',
  nextMonth: 'Дараа сар (PageDown)',
  previousYear: 'Өмнөх жил (Control + left)',
  nextYear: 'Дараа жил (Control + right)',
  previousDecade: 'Өмнөх арван',
  nextDecade: 'Дараа арван',
  previousCentury: 'Өмнөх зуун',
  nextCentury: 'Дараа зуун'
});
var _default = exports.default = locale;