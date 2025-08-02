"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _kn_IN = _interopRequireDefault(require("rc-picker/lib/locale/kn_IN"));
var _kn_IN2 = _interopRequireDefault(require("../../time-picker/locale/kn_IN"));
// Merge into a locale object
const locale = {
  lang: Object.assign({
    placeholder: 'ದಿನಾಂಕ ಆಯ್ಕೆಮಾಡಿ',
    yearPlaceholder: 'ವರ್ಷ ಆಯ್ಕೆಮಾಡಿ',
    rangePlaceholder: ['ಪ್ರಾರಂಭ ದಿನಾಂಕ', 'ಅಂತಿಮ ದಿನಾಂಕ'],
    quarterPlaceholder: 'ಕಾಲುಭಾಗವನ್ನು ಆಯ್ಕೆಮಾಡಿ',
    monthPlaceholder: 'ತಿಂಗಳನ್ನು ಆಯ್ಕೆಮಾಡಿ',
    weekPlaceholder: 'ವಾರವನ್ನು ಆಯ್ಕೆಮಾಡಿ',
    rangeYearPlaceholder: ['ಉದ್ಘಾಟನಾ ವರ್ಷ', 'ಅಂತಿಮ ವರ್ಷ'],
    rangeQuarterPlaceholder: ['ತ್ರೈಮಾಸಿಕದ ಆರಂಭ', 'ಅಂತಿಮ ತ್ರೈಮಾಸಿಕ'],
    rangeMonthPlaceholder: ['ಆರಂಭಿಕ ತಿಂಗಳು', 'ಅಂತಿಮ ತಿಂಗಳು'],
    rangeWeekPlaceholder: ['ತೆರೆಯುವ ವಾರ', 'ಅಂತಿಮ ವಾರ']
  }, _kn_IN.default),
  timePickerLocale: Object.assign({}, _kn_IN2.default)
};
// All settings at:
// https://github.com/ant-design/ant-design/blob/master/components/date-picker/locale/example.json
var _default = exports.default = locale;