"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'uk_UA',
  today: 'Сьогодні',
  now: 'Зараз',
  backToToday: 'Поточна дата',
  ok: 'OK',
  clear: 'Очистити',
  week: 'Тиждень',
  month: 'Місяць',
  year: 'Рік',
  timeSelect: 'Обрати час',
  dateSelect: 'Обрати дату',
  monthSelect: 'Обрати місяць',
  yearSelect: 'Обрати рік',
  decadeSelect: 'Обрати десятиріччя',
  dateFormat: 'D-M-YYYY',
  dateTimeFormat: 'D-M-YYYY HH:mm:ss',
  previousMonth: 'Попередній місяць (PageUp)',
  nextMonth: 'Наступний місяць (PageDown)',
  previousYear: 'Попередній рік (Control + left)',
  nextYear: 'Наступний рік (Control + right)',
  previousDecade: 'Попереднє десятиріччя',
  nextDecade: 'Наступне десятиріччя',
  previousCentury: 'Попереднє століття',
  nextCentury: 'Наступне століття'
});
var _default = exports.default = locale;