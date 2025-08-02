"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _uk_UA = _interopRequireDefault(require("rc-picker/lib/locale/uk_UA"));
var _uk_UA2 = _interopRequireDefault(require("../../time-picker/locale/uk_UA"));
// Merge into a locale object
const locale = {
  lang: Object.assign({
    placeholder: 'Оберіть дату',
    yearPlaceholder: 'Оберіть рік',
    quarterPlaceholder: 'Оберіть квартал',
    monthPlaceholder: 'Оберіть місяць',
    weekPlaceholder: 'Оберіть тиждень',
    rangePlaceholder: ['Початкова дата', 'Кінцева дата'],
    rangeYearPlaceholder: ['Початковий рік', 'Кінцевий рік'],
    rangeMonthPlaceholder: ['Початковий місяць', 'Кінцевий місяць'],
    rangeWeekPlaceholder: ['Початковий тиждень', 'Кінцевий тиждень'],
    shortWeekDays: ['Нд', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'],
    shortMonths: ['Січ', 'Лют', 'Бер', 'Кві', 'Тра', 'Чер', 'Лип', 'Сер', 'Вер', 'Жов', 'Лис', 'Гру']
  }, _uk_UA.default),
  timePickerLocale: Object.assign({}, _uk_UA2.default)
};
// All settings at:
// https://github.com/ant-design/ant-design/blob/master/components/date-picker/locale/example.json
var _default = exports.default = locale;