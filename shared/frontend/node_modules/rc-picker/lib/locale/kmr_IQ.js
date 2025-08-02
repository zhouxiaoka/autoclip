"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'ku',
  today: 'Îro',
  now: 'Niha',
  backToToday: 'Vegere îro',
  ok: 'Temam',
  clear: 'Paqij bike',
  week: 'Sêbê',
  month: 'Meh',
  year: 'Sal',
  timeSelect: 'Demê hilbijêre',
  dateSelect: 'Dîrok hilbijêre',
  monthSelect: 'Meh hilbijêre',
  yearSelect: 'Sal hilbijêre',
  decadeSelect: 'Dehsal hilbijêre',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'Meha peş (PageUp))',
  nextMonth: 'Meha paş (PageDown)',
  previousYear: 'Sala peş (Control + şep)',
  nextYear: 'Sala paş (Control + rast)',
  previousDecade: 'Dehsalen peş',
  nextDecade: 'Dehsalen paş',
  previousCentury: 'Sedsalen peş',
  nextCentury: 'Sedsalen paş'
});
var _default = exports.default = locale;