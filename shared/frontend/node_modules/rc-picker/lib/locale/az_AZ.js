"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'az_AZ',
  today: 'Bugün',
  now: 'İndi',
  backToToday: 'Bugünə qayıt',
  ok: 'Təsdiq',
  clear: 'Təmizlə',
  week: 'Həftə',
  month: 'Ay',
  year: 'İl',
  timeSelect: 'vaxtı seç',
  dateSelect: 'tarixi seç',
  weekSelect: 'Həftə seç',
  monthSelect: 'Ay seç',
  yearSelect: 'il seç',
  decadeSelect: 'Onillik seçin',
  dateFormat: 'D.M.YYYY',
  dateTimeFormat: 'D.M.YYYY HH:mm:ss',
  previousMonth: 'Əvvəlki ay (PageUp)',
  nextMonth: 'Növbəti ay (PageDown)',
  previousYear: 'Sonuncu il (Control + left)',
  nextYear: 'Növbəti il (Control + right)',
  previousDecade: 'Sonuncu onillik',
  nextDecade: 'Növbəti onillik',
  previousCentury: 'Sonuncu əsr',
  nextCentury: 'Növbəti əsr'
});
var _default = exports.default = locale;