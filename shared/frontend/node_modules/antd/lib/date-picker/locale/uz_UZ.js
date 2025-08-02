"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _uz_UZ = _interopRequireDefault(require("rc-picker/lib/locale/uz_UZ"));
var _uz_UZ2 = _interopRequireDefault(require("../../time-picker/locale/uz_UZ"));
// Merge into a locale object
const locale = {
  lang: Object.assign({
    placeholder: 'Sanani tanlang',
    yearPlaceholder: 'Yilni tanlang',
    quarterPlaceholder: 'Chorakni tanlang',
    monthPlaceholder: 'Oyni tanlang',
    weekPlaceholder: 'Haftani tanlang',
    rangePlaceholder: ['Boshlanish sanasi', 'Tugallanish sanasi'],
    rangeYearPlaceholder: ['Boshlanish yili', 'Tugallanish yili'],
    rangeMonthPlaceholder: ['Boshlanish oyi', 'Tugallanish oyi'],
    rangeWeekPlaceholder: ['Boshlanish haftasi', 'Tugallanish haftasi']
  }, _uz_UZ.default),
  timePickerLocale: Object.assign({}, _uz_UZ2.default)
};
// All settings at:
// https://github.com/ant-design/ant-design/blob/master/components/date-picker/locale/example.json
var _default = exports.default = locale;