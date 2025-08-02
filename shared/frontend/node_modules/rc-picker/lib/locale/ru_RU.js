"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'ru_RU',
  today: 'Сегодня',
  now: 'Сейчас',
  backToToday: 'Текущая дата',
  ok: 'ОК',
  clear: 'Очистить',
  week: 'Неделя',
  month: 'Месяц',
  year: 'Год',
  timeSelect: 'Выбрать время',
  dateSelect: 'Выбрать дату',
  monthSelect: 'Выбрать месяц',
  yearSelect: 'Выбрать год',
  decadeSelect: 'Выбрать десятилетие',
  dateFormat: 'D-M-YYYY',
  dateTimeFormat: 'D-M-YYYY HH:mm:ss',
  previousMonth: 'Предыдущий месяц (PageUp)',
  nextMonth: 'Следующий месяц (PageDown)',
  previousYear: 'Предыдущий год (Control + left)',
  nextYear: 'Следующий год (Control + right)',
  previousDecade: 'Предыдущее десятилетие',
  nextDecade: 'Следущее десятилетие',
  previousCentury: 'Предыдущий век',
  nextCentury: 'Следующий век'
});
var _default = exports.default = locale;