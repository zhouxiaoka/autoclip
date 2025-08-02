"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'fi_FI',
  today: 'Tänään',
  now: 'Nyt',
  backToToday: 'Tämä päivä',
  ok: 'OK',
  clear: 'Tyhjennä',
  week: 'Viikko',
  month: 'Kuukausi',
  year: 'Vuosi',
  timeSelect: 'Valise aika',
  dateSelect: 'Valitse päivä',
  monthSelect: 'Valitse kuukausi',
  yearSelect: 'Valitse vuosi',
  decadeSelect: 'Valitse vuosikymmen',
  dateFormat: 'D.M.YYYY',
  dateTimeFormat: 'D.M.YYYY HH:mm:ss',
  previousMonth: 'Edellinen kuukausi (PageUp)',
  nextMonth: 'Seuraava kuukausi (PageDown)',
  previousYear: 'Edellinen vuosi (Control + left)',
  nextYear: 'Seuraava vuosi (Control + right)',
  previousDecade: 'Edellinen vuosikymmen',
  nextDecade: 'Seuraava vuosikymmen',
  previousCentury: 'Edellinen vuosisata',
  nextCentury: 'Seuraava vuosisata'
});
var _default = exports.default = locale;