"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'lv_LV',
  today: 'Šodien',
  now: 'Tagad',
  backToToday: 'Atpakaļ pie šodienas',
  ok: 'OK',
  clear: 'Skaidrs',
  week: 'Nedēļa',
  month: 'Mēnesis',
  year: 'Gads',
  timeSelect: 'Izvēlieties laiku',
  dateSelect: 'Izvēlieties datumu',
  monthSelect: 'Izvēlieties mēnesi',
  yearSelect: 'Izvēlieties gadu',
  decadeSelect: 'Izvēlieties desmit gadus',
  dateFormat: 'D.M.YYYY',
  dateTimeFormat: 'D.M.YYYY HH:mm:ss',
  previousMonth: 'Iepriekšējais mēnesis (PageUp)',
  nextMonth: 'Nākammēnes (PageDown)',
  previousYear: 'Pagājušais gads (Control + left)',
  nextYear: 'Nākamgad (Control + right)',
  previousDecade: 'Pēdējā desmitgadē',
  nextDecade: 'Nākamā desmitgade',
  previousCentury: 'Pagājušajā gadsimtā',
  nextCentury: 'Nākamajā gadsimtā'
});
var _default = exports.default = locale;