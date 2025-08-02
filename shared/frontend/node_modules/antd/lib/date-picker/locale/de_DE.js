"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _de_DE = _interopRequireDefault(require("rc-picker/lib/locale/de_DE"));
var _de_DE2 = _interopRequireDefault(require("../../time-picker/locale/de_DE"));
// Merge into a locale object
const locale = {
  lang: Object.assign({
    placeholder: 'Datum auswählen',
    rangePlaceholder: ['Startdatum', 'Enddatum'],
    shortWeekDays: ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'],
    shortMonths: ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']
  }, _de_DE.default),
  timePickerLocale: Object.assign({}, _de_DE2.default)
};
// All settings at:
// https://github.com/ant-design/ant-design/issues/424
var _default = exports.default = locale;