"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _az_AZ = _interopRequireDefault(require("rc-picker/lib/locale/az_AZ"));
var _az_AZ2 = _interopRequireDefault(require("../../time-picker/locale/az_AZ"));
const locale = {
  lang: Object.assign({
    placeholder: 'Tarix seçin',
    rangePlaceholder: ['Başlama tarixi', 'Bitmə tarixi'],
    yearPlaceholder: 'İl seçin',
    quarterPlaceholder: 'Rüb seçin',
    monthPlaceholder: 'Ay seçin',
    weekPlaceholder: 'Həftə seçin',
    rangeYearPlaceholder: ['Başlama il', 'Bitmə il'],
    rangeQuarterPlaceholder: ['Başlama rüb', 'Bitmə rüb'],
    rangeMonthPlaceholder: ['Başlama ay', 'Bitmə ay'],
    rangeWeekPlaceholder: ['Başlama həftə', 'Bitmə həftə']
  }, _az_AZ.default),
  timePickerLocale: Object.assign({}, _az_AZ2.default)
};
var _default = exports.default = locale;