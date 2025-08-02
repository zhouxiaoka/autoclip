"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'sv_SE',
  today: 'I dag',
  now: 'Nu',
  backToToday: 'Till idag',
  ok: 'OK',
  clear: 'Avbryt',
  week: 'Vecka',
  month: 'Månad',
  year: 'År',
  timeSelect: 'Välj tidpunkt',
  dateSelect: 'Välj datum',
  monthSelect: 'Välj månad',
  yearSelect: 'Välj år',
  decadeSelect: 'Välj årtionde',
  dateFormat: 'YYYY-MM-DD',
  dateTimeFormat: 'YYYY-MM-DD H:mm:ss',
  previousMonth: 'Förra månaden (PageUp)',
  nextMonth: 'Nästa månad (PageDown)',
  previousYear: 'Föreg år (Control + left)',
  nextYear: 'Nästa år (Control + right)',
  previousDecade: 'Föreg årtionde',
  nextDecade: 'Nästa årtionde',
  previousCentury: 'Föreg århundrade',
  nextCentury: 'Nästa århundrade'
});
var _default = exports.default = locale;