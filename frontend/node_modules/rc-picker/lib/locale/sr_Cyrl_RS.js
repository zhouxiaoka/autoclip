"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'sr_Cyrl_RS',
  today: 'Данас',
  now: 'Сада',
  backToToday: 'Врати се на данас',
  ok: 'У реду',
  clear: 'Обриши',
  week: 'Недеља',
  month: 'Месец',
  year: 'Година',
  timeSelect: 'Изабери време',
  dateSelect: 'Изабери датум',
  monthSelect: 'Изабери месец',
  yearSelect: 'Изабери годину',
  decadeSelect: 'Изабери деценију',
  dateFormat: 'DD.MM.YYYY',
  dateTimeFormat: 'DD.MM.YYYY HH:mm:ss',
  previousMonth: 'Претходни месец (PageUp)',
  nextMonth: 'Следећи месец (PageDown)',
  previousYear: 'Претходна година (Control + left)',
  nextYear: 'Следећа година (Control + right)',
  previousDecade: 'Претходна деценија',
  nextDecade: 'Следећа деценија',
  previousCentury: 'Претходни век',
  nextCentury: 'Следећи век'
});
var _default = exports.default = locale;