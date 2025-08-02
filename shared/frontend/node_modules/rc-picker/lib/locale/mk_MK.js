"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'mk_MK',
  today: 'Денес',
  now: 'Сега',
  backToToday: 'Назад до денес',
  ok: 'ОК',
  clear: 'Избриши',
  week: 'Недела',
  month: 'Месец',
  year: 'Година',
  timeSelect: 'Избери време',
  dateSelect: 'Избери датум',
  monthSelect: 'Избери месец',
  yearSelect: 'Избери година',
  decadeSelect: 'Избери деценија',
  dateFormat: 'D.M.YYYY',
  dateTimeFormat: 'D.M.YYYY HH:mm:ss',
  previousMonth: 'Претходен месец (PageUp)',
  nextMonth: 'Нареден месец (PageDown)',
  previousYear: 'Претходна година (Control + left)',
  nextYear: 'Наредна година (Control + right)',
  previousDecade: 'Претходна деценија',
  nextDecade: 'Наредна деценија',
  previousCentury: 'Претходен век',
  nextCentury: 'Нареден век'
});
var _default = exports.default = locale;