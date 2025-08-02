"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'lt_LT',
  today: 'Šiandien',
  now: 'Dabar',
  backToToday: 'Rodyti šiandien',
  ok: 'Gerai',
  clear: 'Išvalyti',
  week: 'Savaitė',
  month: 'Mėnesis',
  year: 'Metai',
  timeSelect: 'Pasirinkti laiką',
  dateSelect: 'Pasirinkti datą',
  weekSelect: 'Pasirinkti savaitę',
  monthSelect: 'Pasirinkti mėnesį',
  yearSelect: 'Pasirinkti metus',
  decadeSelect: 'Pasirinkti dešimtmetį',
  dateFormat: 'YYYY-MM-DD',
  dayFormat: 'DD',
  dateTimeFormat: 'YYYY-MM-DD HH:MM:SS',
  previousMonth: 'Buvęs mėnesis (PageUp)',
  nextMonth: 'Kitas mėnesis (PageDown)',
  previousYear: 'Buvę metai (Control + left)',
  nextYear: 'Kiti metai (Control + right)',
  previousDecade: 'Buvęs dešimtmetis',
  nextDecade: 'Kitas dešimtmetis',
  previousCentury: 'Buvęs amžius',
  nextCentury: 'Kitas amžius'
});
var _default = exports.default = locale;