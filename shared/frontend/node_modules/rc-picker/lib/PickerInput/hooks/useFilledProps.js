"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useFilledProps;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _rcUtil = require("rc-util");
var React = _interopRequireWildcard(require("react"));
var _useLocale = _interopRequireDefault(require("../../hooks/useLocale"));
var _useTimeConfig = require("../../hooks/useTimeConfig");
var _miscUtil = require("../../utils/miscUtil");
var _useClearIcon = require("../Selector/hooks/useClearIcon");
var _useDisabledBoundary = _interopRequireDefault(require("./useDisabledBoundary"));
var _useFieldFormat3 = require("./useFieldFormat");
var _useInputReadOnly = _interopRequireDefault(require("./useInputReadOnly"));
var _useInvalidate = _interopRequireDefault(require("./useInvalidate"));
function useList(value) {
  var fillMode = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : false;
  var values = React.useMemo(function () {
    var list = value ? (0, _miscUtil.toArray)(value) : value;
    if (fillMode && list) {
      list[1] = list[1] || list[0];
    }
    return list;
  }, [value, fillMode]);
  return values;
}

/**
 * Align the outer props with unique typed and fill undefined props.
 * This is shared with both RangePicker and Picker. This will do:
 * - Convert `value` & `defaultValue` to array
 * - handle the legacy props fill like `clearIcon` + `allowClear` = `clearIcon`
 */
function useFilledProps(props, updater) {
  var generateConfig = props.generateConfig,
    locale = props.locale,
    _props$picker = props.picker,
    picker = _props$picker === void 0 ? 'date' : _props$picker,
    _props$prefixCls = props.prefixCls,
    prefixCls = _props$prefixCls === void 0 ? 'rc-picker' : _props$prefixCls,
    _props$styles = props.styles,
    styles = _props$styles === void 0 ? {} : _props$styles,
    _props$classNames = props.classNames,
    classNames = _props$classNames === void 0 ? {} : _props$classNames,
    _props$order = props.order,
    order = _props$order === void 0 ? true : _props$order,
    _props$components = props.components,
    components = _props$components === void 0 ? {} : _props$components,
    inputRender = props.inputRender,
    allowClear = props.allowClear,
    clearIcon = props.clearIcon,
    needConfirm = props.needConfirm,
    multiple = props.multiple,
    format = props.format,
    inputReadOnly = props.inputReadOnly,
    disabledDate = props.disabledDate,
    minDate = props.minDate,
    maxDate = props.maxDate,
    showTime = props.showTime,
    value = props.value,
    defaultValue = props.defaultValue,
    pickerValue = props.pickerValue,
    defaultPickerValue = props.defaultPickerValue;
  var values = useList(value);
  var defaultValues = useList(defaultValue);
  var pickerValues = useList(pickerValue);
  var defaultPickerValues = useList(defaultPickerValue);

  // ======================== Picker ========================
  /** Almost same as `picker`, but add `datetime` for `date` with `showTime` */
  var internalPicker = picker === 'date' && showTime ? 'datetime' : picker;

  /** The picker is `datetime` or `time` */
  var multipleInteractivePicker = internalPicker === 'time' || internalPicker === 'datetime';
  var complexPicker = multipleInteractivePicker || multiple;
  var mergedNeedConfirm = needConfirm !== null && needConfirm !== void 0 ? needConfirm : multipleInteractivePicker;

  // ========================== Time ==========================
  // Auto `format` need to check `showTime.showXXX` first.
  // And then merge the `locale` into `mergedShowTime`.
  var _getTimeProps = (0, _useTimeConfig.getTimeProps)(props),
    _getTimeProps2 = (0, _slicedToArray2.default)(_getTimeProps, 4),
    timeProps = _getTimeProps2[0],
    localeTimeProps = _getTimeProps2[1],
    showTimeFormat = _getTimeProps2[2],
    propFormat = _getTimeProps2[3];

  // ======================= Locales ========================
  var mergedLocale = (0, _useLocale.default)(locale, localeTimeProps);
  var mergedShowTime = React.useMemo(function () {
    return (0, _useTimeConfig.fillShowTimeConfig)(internalPicker, showTimeFormat, propFormat, timeProps, mergedLocale);
  }, [internalPicker, showTimeFormat, propFormat, timeProps, mergedLocale]);

  // ======================= Warning ========================
  if (process.env.NODE_ENV !== 'production' && picker === 'time') {
    if (['disabledHours', 'disabledMinutes', 'disabledSeconds'].some(function (key) {
      return props[key];
    })) {
      (0, _rcUtil.warning)(false, "'disabledHours', 'disabledMinutes', 'disabledSeconds' will be removed in the next major version, please use 'disabledTime' instead.");
    }
  }

  // ======================== Props =========================
  var filledProps = React.useMemo(function () {
    return (0, _objectSpread2.default)((0, _objectSpread2.default)({}, props), {}, {
      prefixCls: prefixCls,
      locale: mergedLocale,
      picker: picker,
      styles: styles,
      classNames: classNames,
      order: order,
      components: (0, _objectSpread2.default)({
        input: inputRender
      }, components),
      clearIcon: (0, _useClearIcon.fillClearIcon)(prefixCls, allowClear, clearIcon),
      showTime: mergedShowTime,
      value: values,
      defaultValue: defaultValues,
      pickerValue: pickerValues,
      defaultPickerValue: defaultPickerValues
    }, updater === null || updater === void 0 ? void 0 : updater());
  }, [props]);

  // ======================== Format ========================
  var _useFieldFormat = (0, _useFieldFormat3.useFieldFormat)(internalPicker, mergedLocale, format),
    _useFieldFormat2 = (0, _slicedToArray2.default)(_useFieldFormat, 2),
    formatList = _useFieldFormat2[0],
    maskFormat = _useFieldFormat2[1];

  // ======================= ReadOnly =======================
  var mergedInputReadOnly = (0, _useInputReadOnly.default)(formatList, inputReadOnly, multiple);

  // ======================= Boundary =======================
  var disabledBoundaryDate = (0, _useDisabledBoundary.default)(generateConfig, locale, disabledDate, minDate, maxDate);

  // ====================== Invalidate ======================
  var isInvalidateDate = (0, _useInvalidate.default)(generateConfig, picker, disabledBoundaryDate, mergedShowTime);

  // ======================== Merged ========================
  var mergedProps = React.useMemo(function () {
    return (0, _objectSpread2.default)((0, _objectSpread2.default)({}, filledProps), {}, {
      needConfirm: mergedNeedConfirm,
      inputReadOnly: mergedInputReadOnly,
      disabledDate: disabledBoundaryDate
    });
  }, [filledProps, mergedNeedConfirm, mergedInputReadOnly, disabledBoundaryDate]);
  return [mergedProps, internalPicker, complexPicker, formatList, maskFormat, isInvalidateDate];
}