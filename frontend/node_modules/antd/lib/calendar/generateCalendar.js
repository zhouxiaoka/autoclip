"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcPicker = require("rc-picker");
var _useMergedState = _interopRequireDefault(require("rc-util/lib/hooks/useMergedState"));
var _warning = require("../_util/warning");
var _context = require("../config-provider/context");
var _locale = require("../locale");
var _Header = _interopRequireDefault(require("./Header"));
var _en_US = _interopRequireDefault(require("./locale/en_US"));
var _style = _interopRequireDefault(require("./style"));
const isSameYear = (date1, date2, config) => {
  const {
    getYear
  } = config;
  return date1 && date2 && getYear(date1) === getYear(date2);
};
const isSameMonth = (date1, date2, config) => {
  const {
    getMonth
  } = config;
  return isSameYear(date1, date2, config) && getMonth(date1) === getMonth(date2);
};
const isSameDate = (date1, date2, config) => {
  const {
    getDate
  } = config;
  return isSameMonth(date1, date2, config) && getDate(date1) === getDate(date2);
};
const generateCalendar = generateConfig => {
  const Calendar = props => {
    const {
      prefixCls: customizePrefixCls,
      className,
      rootClassName,
      style,
      dateFullCellRender,
      dateCellRender,
      monthFullCellRender,
      monthCellRender,
      cellRender,
      fullCellRender,
      headerRender,
      value,
      defaultValue,
      disabledDate,
      mode,
      validRange,
      fullscreen = true,
      showWeek,
      onChange,
      onPanelChange,
      onSelect
    } = props;
    const {
      getPrefixCls,
      direction,
      className: contextClassName,
      style: contextStyle
    } = (0, _context.useComponentConfig)('calendar');
    const prefixCls = getPrefixCls('picker', customizePrefixCls);
    const calendarPrefixCls = `${prefixCls}-calendar`;
    const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls, calendarPrefixCls);
    const today = generateConfig.getNow();
    // ====================== Warning =======================
    if (process.env.NODE_ENV !== 'production') {
      const warning = (0, _warning.devUseWarning)('Calendar');
      [['dateFullCellRender', 'fullCellRender'], ['dateCellRender', 'cellRender'], ['monthFullCellRender', 'fullCellRender'], ['monthCellRender', 'cellRender']].forEach(([deprecatedName, newName]) => {
        warning.deprecated(!(deprecatedName in props), deprecatedName, newName);
      });
    }
    // ====================== State =======================
    // Value
    const [mergedValue, setMergedValue] = (0, _useMergedState.default)(() => value || generateConfig.getNow(), {
      defaultValue,
      value
    });
    // Mode
    const [mergedMode, setMergedMode] = (0, _useMergedState.default)('month', {
      value: mode
    });
    const panelMode = React.useMemo(() => mergedMode === 'year' ? 'month' : 'date', [mergedMode]);
    // Disabled Date
    const mergedDisabledDate = React.useCallback(date => {
      const notInRange = validRange ? generateConfig.isAfter(validRange[0], date) || generateConfig.isAfter(date, validRange[1]) : false;
      return notInRange || !!(disabledDate === null || disabledDate === void 0 ? void 0 : disabledDate(date));
    }, [disabledDate, validRange]);
    // ====================== Events ======================
    const triggerPanelChange = (date, newMode) => {
      onPanelChange === null || onPanelChange === void 0 ? void 0 : onPanelChange(date, newMode);
    };
    const triggerChange = date => {
      setMergedValue(date);
      if (!isSameDate(date, mergedValue, generateConfig)) {
        // Trigger when month panel switch month
        if (panelMode === 'date' && !isSameMonth(date, mergedValue, generateConfig) || panelMode === 'month' && !isSameYear(date, mergedValue, generateConfig)) {
          triggerPanelChange(date, mergedMode);
        }
        onChange === null || onChange === void 0 ? void 0 : onChange(date);
      }
    };
    const triggerModeChange = newMode => {
      setMergedMode(newMode);
      triggerPanelChange(mergedValue, newMode);
    };
    const onInternalSelect = (date, source) => {
      triggerChange(date);
      onSelect === null || onSelect === void 0 ? void 0 : onSelect(date, {
        source
      });
    };
    // ====================== Render ======================
    const dateRender = React.useCallback((date, info) => {
      if (fullCellRender) {
        return fullCellRender(date, info);
      }
      if (dateFullCellRender) {
        return dateFullCellRender(date);
      }
      return /*#__PURE__*/React.createElement("div", {
        className: (0, _classnames.default)(`${prefixCls}-cell-inner`, `${calendarPrefixCls}-date`, {
          [`${calendarPrefixCls}-date-today`]: isSameDate(today, date, generateConfig)
        })
      }, /*#__PURE__*/React.createElement("div", {
        className: `${calendarPrefixCls}-date-value`
      }, String(generateConfig.getDate(date)).padStart(2, '0')), /*#__PURE__*/React.createElement("div", {
        className: `${calendarPrefixCls}-date-content`
      }, cellRender ? cellRender(date, info) : dateCellRender === null || dateCellRender === void 0 ? void 0 : dateCellRender(date)));
    }, [dateFullCellRender, dateCellRender, cellRender, fullCellRender]);
    const monthRender = React.useCallback((date, info) => {
      if (fullCellRender) {
        return fullCellRender(date, info);
      }
      if (monthFullCellRender) {
        return monthFullCellRender(date);
      }
      const months = info.locale.shortMonths || generateConfig.locale.getShortMonths(info.locale.locale);
      return /*#__PURE__*/React.createElement("div", {
        className: (0, _classnames.default)(`${prefixCls}-cell-inner`, `${calendarPrefixCls}-date`, {
          [`${calendarPrefixCls}-date-today`]: isSameMonth(today, date, generateConfig)
        })
      }, /*#__PURE__*/React.createElement("div", {
        className: `${calendarPrefixCls}-date-value`
      }, months[generateConfig.getMonth(date)]), /*#__PURE__*/React.createElement("div", {
        className: `${calendarPrefixCls}-date-content`
      }, cellRender ? cellRender(date, info) : monthCellRender === null || monthCellRender === void 0 ? void 0 : monthCellRender(date)));
    }, [monthFullCellRender, monthCellRender, cellRender, fullCellRender]);
    const [contextLocale] = (0, _locale.useLocale)('Calendar', _en_US.default);
    const locale = Object.assign(Object.assign({}, contextLocale), props.locale);
    const mergedCellRender = (current, info) => {
      if (info.type === 'date') {
        return dateRender(current, info);
      }
      if (info.type === 'month') {
        return monthRender(current, Object.assign(Object.assign({}, info), {
          locale: locale === null || locale === void 0 ? void 0 : locale.lang
        }));
      }
    };
    return wrapCSSVar(/*#__PURE__*/React.createElement("div", {
      className: (0, _classnames.default)(calendarPrefixCls, {
        [`${calendarPrefixCls}-full`]: fullscreen,
        [`${calendarPrefixCls}-mini`]: !fullscreen,
        [`${calendarPrefixCls}-rtl`]: direction === 'rtl'
      }, contextClassName, className, rootClassName, hashId, cssVarCls),
      style: Object.assign(Object.assign({}, contextStyle), style)
    }, headerRender ? headerRender({
      value: mergedValue,
      type: mergedMode,
      onChange: nextDate => {
        onInternalSelect(nextDate, 'customize');
      },
      onTypeChange: triggerModeChange
    }) : (/*#__PURE__*/React.createElement(_Header.default, {
      prefixCls: calendarPrefixCls,
      value: mergedValue,
      generateConfig: generateConfig,
      mode: mergedMode,
      fullscreen: fullscreen,
      locale: locale === null || locale === void 0 ? void 0 : locale.lang,
      validRange: validRange,
      onChange: onInternalSelect,
      onModeChange: triggerModeChange
    })), /*#__PURE__*/React.createElement(_rcPicker.PickerPanel, {
      value: mergedValue,
      prefixCls: prefixCls,
      locale: locale === null || locale === void 0 ? void 0 : locale.lang,
      generateConfig: generateConfig,
      cellRender: mergedCellRender,
      onSelect: nextDate => {
        onInternalSelect(nextDate, panelMode);
      },
      mode: panelMode,
      picker: panelMode,
      disabledDate: mergedDisabledDate,
      hideHeader: true,
      showWeek: showWeek
    })));
  };
  if (process.env.NODE_ENV !== 'production') {
    Calendar.displayName = 'Calendar';
  }
  return Calendar;
};
var _default = exports.default = generateCalendar;