"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'pl_PL',
  today: 'Dzisiaj',
  now: 'Teraz',
  backToToday: 'Ustaw dzisiaj',
  ok: 'OK',
  clear: 'Wyczyść',
  week: 'Tydzień',
  month: 'Miesiąc',
  year: 'Rok',
  timeSelect: 'Ustaw czas',
  dateSelect: 'Ustaw datę',
  monthSelect: 'Wybierz miesiąc',
  yearSelect: 'Wybierz rok',
  decadeSelect: 'Wybierz dekadę',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'Poprzedni miesiąc (PageUp)',
  nextMonth: 'Następny miesiąc (PageDown)',
  previousYear: 'Ostatni rok (Ctrl + left)',
  nextYear: 'Następny rok (Ctrl + right)',
  previousDecade: 'Ostatnia dekada',
  nextDecade: 'Następna dekada',
  previousCentury: 'Ostatni wiek',
  nextCentury: 'Następny wiek'
});
var _default = exports.default = locale;