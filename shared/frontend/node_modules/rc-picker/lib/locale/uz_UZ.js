"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'uz_UZ',
  today: 'Bugun',
  now: 'Hozir',
  backToToday: 'Bugunga qaytish',
  ok: 'OK',
  clear: 'Toza',
  week: 'Xafta',
  month: 'Oy',
  year: 'Yil',
  timeSelect: 'vaqtni tanlang',
  dateSelect: 'sanani tanlang',
  weekSelect: 'Haftani tanlang',
  monthSelect: 'Oyni tanlang',
  yearSelect: 'Yilni tanlang',
  decadeSelect: "O'n yilni tanlang",
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousMonth: 'Oldingi oy (PageUp)',
  nextMonth: 'Keyingi oy (PageDown)',
  previousYear: "O'tgan yili (Control + left)",
  nextYear: 'Keyingi yil (Control + right)',
  previousDecade: "Oxirgi o'n yil",
  nextDecade: "Keyingi o'n yil",
  previousCentury: "O'tgan asr",
  nextCentury: 'Keyingi asr'
});
var _default = exports.default = locale;