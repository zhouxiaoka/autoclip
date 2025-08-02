"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = DateTimePanel;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var React = _interopRequireWildcard(require("react"));
var _useTimeInfo3 = _interopRequireDefault(require("../../hooks/useTimeInfo"));
var _dateUtil = require("../../utils/dateUtil");
var _DatePanel = _interopRequireDefault(require("../DatePanel"));
var _TimePanel = _interopRequireDefault(require("../TimePanel"));
function DateTimePanel(props) {
  var prefixCls = props.prefixCls,
    generateConfig = props.generateConfig,
    showTime = props.showTime,
    onSelect = props.onSelect,
    value = props.value,
    pickerValue = props.pickerValue,
    onHover = props.onHover;
  var panelPrefixCls = "".concat(prefixCls, "-datetime-panel");

  // =============================== Time ===============================
  var _useTimeInfo = (0, _useTimeInfo3.default)(generateConfig, showTime),
    _useTimeInfo2 = (0, _slicedToArray2.default)(_useTimeInfo, 1),
    getValidTime = _useTimeInfo2[0];

  // Merge the time info from `value` or `pickerValue`
  var mergeTime = function mergeTime(date) {
    if (value) {
      return (0, _dateUtil.fillTime)(generateConfig, date, value);
    }
    return (0, _dateUtil.fillTime)(generateConfig, date, pickerValue);
  };

  // ============================== Hover ===============================
  var onDateHover = function onDateHover(date) {
    onHover === null || onHover === void 0 || onHover(date ? mergeTime(date) : date);
  };

  // ============================== Select ==============================
  var onDateSelect = function onDateSelect(date) {
    // Merge with current time
    var cloneDate = mergeTime(date);
    onSelect(getValidTime(cloneDate, cloneDate));
  };

  // ============================== Render ==============================
  return /*#__PURE__*/React.createElement("div", {
    className: panelPrefixCls
  }, /*#__PURE__*/React.createElement(_DatePanel.default, (0, _extends2.default)({}, props, {
    onSelect: onDateSelect,
    onHover: onDateHover
  })), /*#__PURE__*/React.createElement(_TimePanel.default, props));
}