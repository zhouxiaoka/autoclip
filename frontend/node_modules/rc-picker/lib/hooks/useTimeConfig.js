"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.fillShowTimeConfig = fillShowTimeConfig;
exports.getTimeProps = getTimeProps;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _typeof2 = _interopRequireDefault(require("@babel/runtime/helpers/typeof"));
var _miscUtil = require("../utils/miscUtil");
var _useLocale = require("./useLocale");
function checkShow(format, keywords, show) {
  return show !== null && show !== void 0 ? show : keywords.some(function (keyword) {
    return format.includes(keyword);
  });
}
var showTimeKeys = [
// 'format',
'showNow', 'showHour', 'showMinute', 'showSecond', 'showMillisecond', 'use12Hours', 'hourStep', 'minuteStep', 'secondStep', 'millisecondStep', 'hideDisabledOptions', 'defaultValue', 'disabledHours', 'disabledMinutes', 'disabledSeconds', 'disabledMilliseconds', 'disabledTime', 'changeOnScroll', 'defaultOpenValue'];

/**
 * Get SharedTimeProps from props.
 */
function pickTimeProps(props) {
  var timeProps = (0, _miscUtil.pickProps)(props, showTimeKeys);
  var format = props.format,
    picker = props.picker;
  var propFormat = null;
  if (format) {
    propFormat = format;
    if (Array.isArray(propFormat)) {
      propFormat = propFormat[0];
    }
    propFormat = (0, _typeof2.default)(propFormat) === 'object' ? propFormat.format : propFormat;
  }
  if (picker === 'time') {
    timeProps.format = propFormat;
  }
  return [timeProps, propFormat];
}
function isStringFormat(format) {
  return format && typeof format === 'string';
}
/** Check if all the showXXX is `undefined` */
function existShowConfig(showHour, showMinute, showSecond, showMillisecond) {
  return [showHour, showMinute, showSecond, showMillisecond].some(function (show) {
    return show !== undefined;
  });
}

/** Fill the showXXX if needed */
function fillShowConfig(hasShowConfig, showHour, showMinute, showSecond, showMillisecond) {
  var parsedShowHour = showHour;
  var parsedShowMinute = showMinute;
  var parsedShowSecond = showSecond;
  if (!hasShowConfig && !parsedShowHour && !parsedShowMinute && !parsedShowSecond && !showMillisecond) {
    parsedShowHour = true;
    parsedShowMinute = true;
    parsedShowSecond = true;
  } else if (hasShowConfig) {
    var _parsedShowHour, _parsedShowMinute, _parsedShowSecond;
    var existFalse = [parsedShowHour, parsedShowMinute, parsedShowSecond].some(function (show) {
      return show === false;
    });
    var existTrue = [parsedShowHour, parsedShowMinute, parsedShowSecond].some(function (show) {
      return show === true;
    });
    var defaultShow = existFalse ? true : !existTrue;
    parsedShowHour = (_parsedShowHour = parsedShowHour) !== null && _parsedShowHour !== void 0 ? _parsedShowHour : defaultShow;
    parsedShowMinute = (_parsedShowMinute = parsedShowMinute) !== null && _parsedShowMinute !== void 0 ? _parsedShowMinute : defaultShow;
    parsedShowSecond = (_parsedShowSecond = parsedShowSecond) !== null && _parsedShowSecond !== void 0 ? _parsedShowSecond : defaultShow;
  }
  return [parsedShowHour, parsedShowMinute, parsedShowSecond, showMillisecond];
}

/**
 * Get `showHour`, `showMinute`, `showSecond` or other from the props.
 * This is pure function, will not get `showXXX` from the `format` prop.
 */
function getTimeProps(componentProps) {
  var showTime = componentProps.showTime;
  var _pickTimeProps = pickTimeProps(componentProps),
    _pickTimeProps2 = (0, _slicedToArray2.default)(_pickTimeProps, 2),
    pickedProps = _pickTimeProps2[0],
    propFormat = _pickTimeProps2[1];
  var showTimeConfig = showTime && (0, _typeof2.default)(showTime) === 'object' ? showTime : {};
  var timeConfig = (0, _objectSpread2.default)((0, _objectSpread2.default)({
    defaultOpenValue: showTimeConfig.defaultOpenValue || showTimeConfig.defaultValue
  }, pickedProps), showTimeConfig);
  var showMillisecond = timeConfig.showMillisecond;
  var showHour = timeConfig.showHour,
    showMinute = timeConfig.showMinute,
    showSecond = timeConfig.showSecond;
  var hasShowConfig = existShowConfig(showHour, showMinute, showSecond, showMillisecond);
  var _fillShowConfig = fillShowConfig(hasShowConfig, showHour, showMinute, showSecond, showMillisecond);
  var _fillShowConfig2 = (0, _slicedToArray2.default)(_fillShowConfig, 3);
  showHour = _fillShowConfig2[0];
  showMinute = _fillShowConfig2[1];
  showSecond = _fillShowConfig2[2];
  return [timeConfig, (0, _objectSpread2.default)((0, _objectSpread2.default)({}, timeConfig), {}, {
    showHour: showHour,
    showMinute: showMinute,
    showSecond: showSecond,
    showMillisecond: showMillisecond
  }), timeConfig.format, propFormat];
}
function fillShowTimeConfig(picker, showTimeFormat, propFormat, timeConfig, locale) {
  var isTimePicker = picker === 'time';
  if (picker === 'datetime' || isTimePicker) {
    var pickedProps = timeConfig;

    // ====================== BaseFormat ======================
    var defaultLocaleFormat = (0, _miscUtil.getRowFormat)(picker, locale, null);
    var baselineFormat = defaultLocaleFormat;
    var formatList = [showTimeFormat, propFormat];
    for (var i = 0; i < formatList.length; i += 1) {
      var format = (0, _miscUtil.toArray)(formatList[i])[0];
      if (isStringFormat(format)) {
        baselineFormat = format;
        break;
      }
    }

    // ========================= Show =========================
    var showHour = pickedProps.showHour,
      showMinute = pickedProps.showMinute,
      showSecond = pickedProps.showSecond,
      showMillisecond = pickedProps.showMillisecond;
    var use12Hours = pickedProps.use12Hours;
    var showMeridiem = checkShow(baselineFormat, ['a', 'A', 'LT', 'LLL', 'LTS'], use12Hours);
    var hasShowConfig = existShowConfig(showHour, showMinute, showSecond, showMillisecond);

    // Fill with format, if needed
    if (!hasShowConfig) {
      showHour = checkShow(baselineFormat, ['H', 'h', 'k', 'LT', 'LLL']);
      showMinute = checkShow(baselineFormat, ['m', 'LT', 'LLL']);
      showSecond = checkShow(baselineFormat, ['s', 'LTS']);
      showMillisecond = checkShow(baselineFormat, ['SSS']);
    }

    // Fallback if all can not see
    // ======================== Format ========================
    var _fillShowConfig3 = fillShowConfig(hasShowConfig, showHour, showMinute, showSecond, showMillisecond);
    var _fillShowConfig4 = (0, _slicedToArray2.default)(_fillShowConfig3, 3);
    showHour = _fillShowConfig4[0];
    showMinute = _fillShowConfig4[1];
    showSecond = _fillShowConfig4[2];
    var timeFormat = showTimeFormat || (0, _useLocale.fillTimeFormat)(showHour, showMinute, showSecond, showMillisecond, showMeridiem);

    // ======================== Props =========================
    return (0, _objectSpread2.default)((0, _objectSpread2.default)({}, pickedProps), {}, {
      // Format
      format: timeFormat,
      // Show Config
      showHour: showHour,
      showMinute: showMinute,
      showSecond: showSecond,
      showMillisecond: showMillisecond,
      use12Hours: showMeridiem
    });
  }
  return null;
}