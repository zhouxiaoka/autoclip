"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'ug_CN',
  today: 'بۈگۈن',
  now: 'ھازىر',
  backToToday: 'بۈگۈنگە قايتىش',
  ok: 'مۇقىملاشتۇرۇش',
  timeSelect: 'ۋاقىت تاللاش',
  dateSelect: 'كۈن تاللاش',
  clear: 'تازىلاش',
  week: 'ھەپتە',
  month: 'ئاي',
  year: 'يىل',
  previousMonth: 'ئالدىنقى ئاي(ئالدىنقى بەت )',
  nextMonth: 'كېلەركى ئاي (كېلەركى بەت)',
  monthSelect: 'ئاي تاللاش',
  yearSelect: 'يىل تاللاش',
  decadeSelect: 'يىللارنى تاللاش',
  yearFormat: 'YYYY-يىلى',
  dayFormat: 'D-كۈنى',
  dateFormat: 'YYYY-يىلىM-ئاينىڭD-كۈنى',
  dateTimeFormat: 'YYYY-يىلىM—ئاينىڭD-كۈنى، HH:mm:ss',
  previousYear: 'ئالدىنقى يىلى (Controlبىلەن يۆنىلىش كونۇپكىسى)',
  nextYear: 'كېلەركى يىلى (Controlبىلەن يۆنىلىش كونۇپكىسى)',
  previousDecade: 'ئالدىنقى يىللار',
  nextDecade: 'كېيىنكى يىللار',
  previousCentury: 'ئالدىنقى ئەسىر',
  nextCentury: 'كېيىنكى ئەسىر',
  monthBeforeYear: false
});
var _default = exports.default = locale;