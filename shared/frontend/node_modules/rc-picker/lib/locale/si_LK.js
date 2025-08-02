"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'si_LK',
  today: 'අද',
  now: 'දැන්',
  backToToday: 'අදට ආපසු',
  ok: 'හරි',
  clear: 'හිස් කරන්න',
  week: 'සතිය',
  month: 'මාසය',
  year: 'අවුරුද්ද',
  timeSelect: 'වේලාවක් තෝරන්න',
  dateSelect: 'දිනයක් තෝරන්න',
  weekSelect: 'සතියක් තෝරන්න',
  monthSelect: 'මාසයක් තෝරන්න',
  yearSelect: 'අවුරුද්දක් තෝරන්න',
  decadeSelect: 'දශකයක් තෝරන්න',
  dateFormat: 'YYYY/M/D',
  dateTimeFormat: 'YYYY/M/D HH:mm:ss',
  monthBeforeYear: false,
  previousMonth: 'කලින් මාසය (පිටුව ඉහළට)',
  nextMonth: 'ඊළඟ මාසය (පිටුව පහළට)',
  previousYear: 'පසුගිය අවුරුද්ද (Control + වම)',
  nextYear: 'ඊළඟ අවුරුද්ද (Control + දකුණ)',
  previousDecade: 'පසුගිය දශකය',
  nextDecade: 'ඊළඟ දශකය',
  previousCentury: 'පසුගිය සියවස',
  nextCentury: 'ඊළඟ සියවස'
});
var _default = exports.default = locale;