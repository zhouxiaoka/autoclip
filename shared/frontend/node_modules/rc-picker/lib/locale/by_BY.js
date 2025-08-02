"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'by_BY',
  today: 'Сёння',
  now: 'Зараз',
  backToToday: 'Дадзеная дата',
  ok: 'OK',
  clear: 'Ачысціць',
  week: 'Тыдзень',
  month: 'Месяц',
  year: 'Год',
  timeSelect: 'Выбраць час',
  dateSelect: 'Выбраць дату',
  weekSelect: 'Выбраць тыдзень',
  monthSelect: 'Выбраць месяц',
  yearSelect: 'Выбраць год',
  decadeSelect: 'Выбраць дзесяцігоддзе',
  dateFormat: 'D-M-YYYY',
  dateTimeFormat: 'D-M-YYYY HH:mm:ss',
  previousMonth: 'Папярэдні месяц (PageUp)',
  nextMonth: 'Наступны месяц (PageDown)',
  previousYear: 'Папярэдні год (Control + left)',
  nextYear: 'Наступны год (Control + right)',
  previousDecade: 'Папярэдняе дзесяцігоддзе',
  nextDecade: 'Наступнае дзесяцігоддзе',
  previousCentury: 'Папярэдні век',
  nextCentury: 'Наступны век'
});
var _default = exports.default = locale;