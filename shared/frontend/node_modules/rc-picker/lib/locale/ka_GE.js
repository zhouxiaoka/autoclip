"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'ka_GE',
  today: 'დღეს',
  now: 'ახლა',
  backToToday: 'მიმდინარე თარიღი',
  ok: 'OK',
  clear: 'გასუფთავება',
  week: 'კვირა',
  month: 'თვე',
  year: 'წელი',
  timeSelect: 'დროის არჩევა',
  dateSelect: 'თარიღის არჩევა',
  weekSelect: 'კვირის არჩევა',
  monthSelect: 'თვის არჩევა',
  yearSelect: 'წლის არჩევა',
  decadeSelect: 'ათწლეულის არჩევა',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousMonth: 'წინა თვე (PageUp)',
  nextMonth: 'მომდევნო თვე (PageDown)',
  previousYear: 'წინა წელი (Control + left)',
  nextYear: 'მომდევნო წელი (Control + right)',
  previousDecade: 'წინა ათწლეული',
  nextDecade: 'მომდევნო ათწლეული',
  previousCentury: 'გასული საუკუნე',
  nextCentury: 'მომდევნო საუკუნე'
});
var _default = exports.default = locale;