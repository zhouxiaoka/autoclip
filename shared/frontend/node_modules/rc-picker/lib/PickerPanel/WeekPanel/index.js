"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = WeekPanel;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _classnames = _interopRequireDefault(require("classnames"));
var React = _interopRequireWildcard(require("react"));
var _dateUtil = require("../../utils/dateUtil");
var _DatePanel = _interopRequireDefault(require("../DatePanel"));
function WeekPanel(props) {
  var prefixCls = props.prefixCls,
    generateConfig = props.generateConfig,
    locale = props.locale,
    value = props.value,
    hoverValue = props.hoverValue,
    hoverRangeValue = props.hoverRangeValue;

  // =============================== Row ================================
  var localeName = locale.locale;
  var rowPrefixCls = "".concat(prefixCls, "-week-panel-row");
  var rowClassName = function rowClassName(currentDate) {
    var rangeCls = {};
    if (hoverRangeValue) {
      var _hoverRangeValue = (0, _slicedToArray2.default)(hoverRangeValue, 2),
        rangeStart = _hoverRangeValue[0],
        rangeEnd = _hoverRangeValue[1];
      var isRangeStart = (0, _dateUtil.isSameWeek)(generateConfig, localeName, rangeStart, currentDate);
      var isRangeEnd = (0, _dateUtil.isSameWeek)(generateConfig, localeName, rangeEnd, currentDate);
      rangeCls["".concat(rowPrefixCls, "-range-start")] = isRangeStart;
      rangeCls["".concat(rowPrefixCls, "-range-end")] = isRangeEnd;
      rangeCls["".concat(rowPrefixCls, "-range-hover")] = !isRangeStart && !isRangeEnd && (0, _dateUtil.isInRange)(generateConfig, rangeStart, rangeEnd, currentDate);
    }
    if (hoverValue) {
      rangeCls["".concat(rowPrefixCls, "-hover")] = hoverValue.some(function (date) {
        return (0, _dateUtil.isSameWeek)(generateConfig, localeName, currentDate, date);
      });
    }
    return (0, _classnames.default)(rowPrefixCls, (0, _defineProperty2.default)({}, "".concat(rowPrefixCls, "-selected"), !hoverRangeValue && (0, _dateUtil.isSameWeek)(generateConfig, localeName, value, currentDate)),
    // Patch for hover range
    rangeCls);
  };

  // ============================== Render ==============================
  return /*#__PURE__*/React.createElement(_DatePanel.default, (0, _extends2.default)({}, props, {
    mode: "week",
    panelName: "week",
    rowClassName: rowClassName
  }));
}