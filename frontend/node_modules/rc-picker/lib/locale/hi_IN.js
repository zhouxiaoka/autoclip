"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'hi_IN',
  today: 'आज',
  now: 'अभी',
  backToToday: 'आज तक',
  ok: 'ठीक',
  clear: 'स्पष्ट',
  week: 'सप्ताह',
  month: 'महीना',
  year: 'साल',
  timeSelect: 'समय का चयन करें',
  dateSelect: 'तारीख़ चुनें',
  weekSelect: 'एक सप्ताह चुनें',
  monthSelect: 'एक महीना चुनें',
  yearSelect: 'एक वर्ष चुनें',
  decadeSelect: 'एक दशक चुनें',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousMonth: 'पिछला महीना (पेजअप)',
  nextMonth: 'अगले महीने (पेजडाउन)',
  previousYear: 'पिछले साल (Ctrl + बाएं)',
  nextYear: 'अगले साल (Ctrl + दाहिना)',
  previousDecade: 'पिछला दशक',
  nextDecade: 'अगले दशक',
  previousCentury: 'पीछ्ली शताब्दी',
  nextCentury: 'अगली सदी'
});
var _default = exports.default = locale;