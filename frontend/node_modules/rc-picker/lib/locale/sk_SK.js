"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'sk_SK',
  today: 'Dnes',
  now: 'Teraz',
  backToToday: 'Späť na dnes',
  ok: 'OK',
  clear: 'Vymazať',
  week: 'Týždeň',
  month: 'Mesiac',
  year: 'Rok',
  timeSelect: 'Vybrať čas',
  dateSelect: 'Vybrať dátum',
  monthSelect: 'Vybrať mesiac',
  yearSelect: 'Vybrať rok',
  decadeSelect: 'Vybrať dekádu',
  dateFormat: 'D.M.YYYY',
  dateTimeFormat: 'D.M.YYYY HH:mm:ss',
  previousMonth: 'Predchádzajúci mesiac (PageUp)',
  nextMonth: 'Nasledujúci mesiac (PageDown)',
  previousYear: 'Predchádzajúci rok (Control + left)',
  nextYear: 'Nasledujúci rok (Control + right)',
  previousDecade: 'Predchádzajúca dekáda',
  nextDecade: 'Nasledujúca dekáda',
  previousCentury: 'Predchádzajúce storočie',
  nextCentury: 'Nasledujúce storočie'
});
var _default = exports.default = locale;