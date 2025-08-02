"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'el_GR',
  today: 'Σήμερα',
  now: 'Τώρα',
  backToToday: 'Πίσω στη σημερινή μέρα',
  ok: 'OK',
  clear: 'Καθαρισμός',
  week: 'Εβδομάδα',
  month: 'Μήνας',
  year: 'Έτος',
  timeSelect: 'Επιλογή ώρας',
  dateSelect: 'Επιλογή ημερομηνίας',
  monthSelect: 'Επιλογή μήνα',
  yearSelect: 'Επιλογή έτους',
  decadeSelect: 'Επιλογή δεκαετίας',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'Προηγούμενος μήνας (PageUp)',
  nextMonth: 'Επόμενος μήνας (PageDown)',
  previousYear: 'Προηγούμενο έτος (Control + αριστερά)',
  nextYear: 'Επόμενο έτος (Control + δεξιά)',
  previousDecade: 'Προηγούμενη δεκαετία',
  nextDecade: 'Επόμενη δεκαετία',
  previousCentury: 'Προηγούμενος αιώνας',
  nextCentury: 'Επόμενος αιώνας'
});
var _default = exports.default = locale;