"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _dayjs = _interopRequireDefault(require("rc-picker/lib/generate/dayjs"));
var _PurePanel = _interopRequireDefault(require("../_util/PurePanel"));
var _generatePicker = _interopRequireDefault(require("./generatePicker"));
const DatePicker = (0, _generatePicker.default)(_dayjs.default);
// We don't care debug panel
/* istanbul ignore next */
const PurePanel = (0, _PurePanel.default)(DatePicker, 'popupAlign', undefined, 'picker');
DatePicker._InternalPanelDoNotUseOrYouWillBeFired = PurePanel;
const PureRangePanel = (0, _PurePanel.default)(DatePicker.RangePicker, 'popupAlign', undefined, 'picker');
DatePicker._InternalRangePanelDoNotUseOrYouWillBeFired = PureRangePanel;
DatePicker.generatePicker = _generatePicker.default;
var _default = exports.default = DatePicker;