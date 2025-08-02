"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'sr_RS',
  today: 'Danas',
  now: 'Sada',
  backToToday: 'Vrati se na danas',
  ok: 'U redu',
  clear: 'Obriši',
  week: 'Nedelja',
  month: 'Mesec',
  year: 'Godina',
  timeSelect: 'Izaberi vreme',
  dateSelect: 'Izaberi datum',
  monthSelect: 'Izaberi mesec',
  yearSelect: 'Izaberi godinu',
  decadeSelect: 'Izaberi deceniju',
  dateFormat: 'DD.MM.YYYY',
  dateTimeFormat: 'DD.MM.YYYY HH:mm:ss',
  previousMonth: 'Prethodni mesec (PageUp)',
  nextMonth: 'Sledeći mesec (PageDown)',
  previousYear: 'Prethodna godina (Control + left)',
  nextYear: 'Sledeća godina (Control + right)',
  previousDecade: 'Prethodna decenija',
  nextDecade: 'Sledeća decenija',
  previousCentury: 'Prethodni vek',
  nextCentury: 'Sledeći vek'
});
var _default = exports.default = locale;