"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'hu_HU',
  today: 'Ma',
  // 'Today',
  now: 'Most',
  // 'Now',
  backToToday: 'Vissza a mai napra',
  // 'Back to today',
  ok: 'OK',
  clear: 'Törlés',
  // 'Clear',
  week: 'Hét',
  month: 'Hónap',
  // 'Month',
  year: 'Év',
  // 'Year',
  timeSelect: 'Időpont kiválasztása',
  // 'Select time',
  dateSelect: 'Dátum kiválasztása',
  // 'Select date',
  monthSelect: 'Hónap kiválasztása',
  // 'Choose a month',
  yearSelect: 'Év kiválasztása',
  // 'Choose a year',
  decadeSelect: 'Évtized kiválasztása',
  // 'Choose a decade',

  dateFormat: 'YYYY/MM/DD',
  // 'M/D/YYYY',
  dayFormat: 'DD',
  // 'D',
  dateTimeFormat: 'YYYY/MM/DD HH:mm:ss',
  // 'M/D/YYYY HH:mm:ss',

  previousMonth: 'Előző hónap (PageUp)',
  // 'Previous month (PageUp)',
  nextMonth: 'Következő hónap (PageDown)',
  // 'Next month (PageDown)',
  previousYear: 'Múlt év (Control + left)',
  // 'Last year (Control + left)',
  nextYear: 'Jövő év (Control + right)',
  // 'Next year (Control + right)',
  previousDecade: 'Előző évtized',
  // 'Last decade',
  nextDecade: 'Következő évtized',
  // 'Next decade',
  previousCentury: 'Múlt évszázad',
  // 'Last century',
  nextCentury: 'Jövő évszázad' // 'Next century',
});
var _default = exports.default = locale;