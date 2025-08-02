"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'gl_ES',
  today: 'Hoxe',
  now: 'Agora',
  backToToday: 'Voltar a hoxe',
  ok: 'Aceptar',
  clear: 'Limpar',
  week: 'Semana',
  month: 'Mes',
  year: 'Ano',
  timeSelect: 'Seleccionar hora',
  dateSelect: 'Seleccionar data',
  monthSelect: 'Elexir un mes',
  yearSelect: 'Elexir un año',
  decadeSelect: 'Elexir unha década',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'Mes anterior (PageUp)',
  nextMonth: 'Mes seguinte (PageDown)',
  previousYear: 'Ano anterior (Control + left)',
  nextYear: 'Ano seguinte (Control + right)',
  previousDecade: 'Década anterior',
  nextDecade: 'Década seguinte',
  previousCentury: 'Século anterior',
  nextCentury: 'Século seguinte'
});
var _default = exports.default = locale;