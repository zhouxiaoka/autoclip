"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'is_IS',
  today: 'Í dag',
  now: 'Núna',
  backToToday: 'Til baka til dagsins í dag',
  ok: 'Í lagi',
  clear: 'Hreinsa',
  week: 'Vika',
  month: 'Mánuður',
  year: 'Ár',
  timeSelect: 'Velja tíma',
  dateSelect: 'Velja dag',
  monthSelect: 'Velja mánuð',
  yearSelect: 'Velja ár',
  decadeSelect: 'Velja áratug',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'Fyrri mánuður (PageUp)',
  nextMonth: 'Næsti mánuður (PageDown)',
  previousYear: 'Fyrra ár (Control + left)',
  nextYear: 'Næsta ár (Control + right)',
  previousDecade: 'Fyrri áratugur',
  nextDecade: 'Næsti áratugur',
  previousCentury: 'Fyrri öld',
  nextCentury: 'Næsta öld'
});
var _default = exports.default = locale;