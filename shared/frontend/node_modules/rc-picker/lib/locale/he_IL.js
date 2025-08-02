"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'he_IL',
  today: 'היום',
  now: 'עכשיו',
  backToToday: 'חזור להיום',
  ok: 'אישור',
  clear: 'איפוס',
  week: 'שבוע',
  month: 'חודש',
  year: 'שנה',
  timeSelect: 'בחר שעה',
  dateSelect: 'בחר תאריך',
  weekSelect: 'בחר שבוע',
  monthSelect: 'בחר חודש',
  yearSelect: 'בחר שנה',
  decadeSelect: 'בחר עשור',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousMonth: 'חודש קודם (PageUp)',
  nextMonth: 'חודש הבא (PageDown)',
  previousYear: 'שנה שעברה (Control + left)',
  nextYear: 'שנה הבאה (Control + right)',
  previousDecade: 'העשור הקודם',
  nextDecade: 'העשור הבא',
  previousCentury: 'המאה הקודמת',
  nextCentury: 'המאה הבאה'
});
var _default = exports.default = locale;