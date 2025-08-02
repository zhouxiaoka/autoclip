"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _ja_JP = _interopRequireDefault(require("rc-picker/lib/locale/ja_JP"));
var _ja_JP2 = _interopRequireDefault(require("../../time-picker/locale/ja_JP"));
// Merge into a locale object
const locale = {
  lang: Object.assign({
    placeholder: '日付を選択',
    yearPlaceholder: '年を選択',
    quarterPlaceholder: '四半期を選択',
    monthPlaceholder: '月を選択',
    weekPlaceholder: '週を選択',
    rangePlaceholder: ['開始日付', '終了日付'],
    rangeYearPlaceholder: ['開始年', '終了年'],
    rangeMonthPlaceholder: ['開始月', '終了月'],
    rangeQuarterPlaceholder: ['開始四半期', '終了四半期'],
    rangeWeekPlaceholder: ['開始週', '終了週'],
    shortWeekDays: ['日', '月', '火', '水', '木', '金', '土'],
    shortMonths: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
  }, _ja_JP.default),
  timePickerLocale: Object.assign({}, _ja_JP2.default)
};
// All settings at:
// https://github.com/ant-design/ant-design/blob/master/components/date-picker/locale/example.json
var _default = exports.default = locale;