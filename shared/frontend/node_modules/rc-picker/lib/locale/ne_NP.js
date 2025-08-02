"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'ne_NP',
  today: 'आज',
  now: 'अब',
  backToToday: 'आज फर्कनुहोस्',
  ok: 'ठिक छ',
  clear: 'खाली गर्नुहोस्',
  week: 'हप्ता',
  month: 'महिना',
  year: 'वर्ष',
  timeSelect: 'समय चयन गर्नुहोस्',
  dateSelect: 'मिति चयन गर्नुहोस्',
  weekSelect: 'एक हप्ता छान्नुहोस्',
  monthSelect: 'एक महिना छान्नुहोस्',
  yearSelect: 'एक वर्ष छान्नुहोस्',
  decadeSelect: 'एक दशक छान्नुहोस्',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousMonth: 'अघिल्लो महिना (पृष्ठ माथि)',
  nextMonth: 'अर्को महिना (पृष्ठ तल)',
  previousYear: 'गत वर्ष (Control + left)',
  nextYear: 'आउने साल (Control + right)',
  previousDecade: 'पछिल्लो दशक',
  nextDecade: 'अर्को दशक',
  previousCentury: 'पछिल्लो शताब्दी',
  nextCentury: 'अर्को शताब्दी'
});
var _default = exports.default = locale;