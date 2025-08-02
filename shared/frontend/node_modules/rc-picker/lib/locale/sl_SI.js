"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'sl_SI',
  today: 'Danes',
  now: 'Trenutno',
  backToToday: 'Nazaj na danes',
  ok: 'V redu',
  clear: 'Počisti',
  week: 'Teden',
  month: 'Mesec',
  year: 'Leto',
  timeSelect: 'Izberite čas',
  dateSelect: 'Izberite datum',
  monthSelect: 'Izberite mesec',
  yearSelect: 'Izberite leto',
  decadeSelect: 'Izberite desetletje',
  dateFormat: 'DD.MM.YYYY',
  dateTimeFormat: 'DD.MM.YYYY HH:mm:ss',
  previousMonth: 'Prejšnji mesec (PageUp)',
  nextMonth: 'Naslednji mesec (PageDown)',
  previousYear: 'Prejšnje leto (Control + left)',
  nextYear: 'Naslednje leto (Control + right)',
  previousDecade: 'Prejšnje desetletje',
  nextDecade: 'Naslednje desetletje',
  previousCentury: 'Prejšnje stoletje',
  nextCentury: 'Naslednje stoletje'
});
var _default = exports.default = locale;