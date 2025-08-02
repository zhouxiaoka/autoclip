"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'kn_IN',
  today: 'ಇಂದು',
  now: 'ಈಗ',
  backToToday: 'ಇಂದು ಹಿಂದಿರುಗಿ',
  ok: 'ಸರಿ',
  clear: 'ಸ್ಪಷ್ಟ',
  week: 'ವಾರ',
  month: 'ತಿಂಗಳು',
  year: 'ವರ್ಷ',
  timeSelect: 'ಸಮಯ ಆಯ್ಕೆಮಾಡಿ',
  dateSelect: 'ದಿನಾಂಕವನ್ನು ಆಯ್ಕೆ ಮಾಡಿ',
  weekSelect: 'ಒಂದು ವಾರದ ಆರಿಸಿ',
  monthSelect: 'ಒಂದು ತಿಂಗಳು ಆಯ್ಕೆಮಾಡಿ',
  yearSelect: 'ಒಂದು ವರ್ಷ ಆರಿಸಿ',
  decadeSelect: 'ಒಂದು ದಶಕದ ಆಯ್ಕೆಮಾಡಿ',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousMonth: 'ಹಿಂದಿನ ತಿಂಗಳು (ಪೇಜ್ಅಪ್)',
  nextMonth: 'ಮುಂದಿನ ತಿಂಗಳು (ಪೇಜ್ಡೌನ್)',
  previousYear: 'ಕಳೆದ ವರ್ಷ (Ctrl + ಎಡ)',
  nextYear: 'ಮುಂದಿನ ವರ್ಷ (Ctrl + ಬಲ)',
  previousDecade: 'ಕಳೆದ ದಶಕ',
  nextDecade: 'ಮುಂದಿನ ದಶಕ',
  previousCentury: 'ಕಳೆದ ಶತಮಾನ',
  nextCentury: 'ಮುಂದಿನ ಶತಮಾನ'
});
var _default = exports.default = locale;