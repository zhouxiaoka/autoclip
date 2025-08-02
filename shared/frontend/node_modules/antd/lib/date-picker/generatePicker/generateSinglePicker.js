"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireWildcard(require("react"));
var React = _react;
var _CalendarOutlined = _interopRequireDefault(require("@ant-design/icons/CalendarOutlined"));
var _ClockCircleOutlined = _interopRequireDefault(require("@ant-design/icons/ClockCircleOutlined"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcPicker = _interopRequireDefault(require("rc-picker"));
var _ContextIsolator = _interopRequireDefault(require("../../_util/ContextIsolator"));
var _useZIndex = require("../../_util/hooks/useZIndex");
var _statusUtils = require("../../_util/statusUtils");
var _warning = require("../../_util/warning");
var _configProvider = require("../../config-provider");
var _DisabledContext = _interopRequireDefault(require("../../config-provider/DisabledContext"));
var _useCSSVarCls = _interopRequireDefault(require("../../config-provider/hooks/useCSSVarCls"));
var _useSize = _interopRequireDefault(require("../../config-provider/hooks/useSize"));
var _context = require("../../form/context");
var _useVariants = _interopRequireDefault(require("../../form/hooks/useVariants"));
var _locale = require("../../locale");
var _Compact = require("../../space/Compact");
var _en_US = _interopRequireDefault(require("../locale/en_US"));
var _style = _interopRequireDefault(require("../style"));
var _util = require("../util");
var _constant = require("./constant");
var _useComponents = _interopRequireDefault(require("./useComponents"));
var _useMergedPickerSemantic = _interopRequireDefault(require("../hooks/useMergedPickerSemantic"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const generatePicker = generateConfig => {
  const getPicker = (picker, displayName) => {
    const consumerName = displayName === _constant.TIMEPICKER ? 'timePicker' : 'datePicker';
    const Picker = /*#__PURE__*/(0, _react.forwardRef)((props, ref) => {
      var _a;
      const {
          prefixCls: customizePrefixCls,
          getPopupContainer: customizeGetPopupContainer,
          components,
          style,
          className,
          rootClassName,
          size: customizeSize,
          bordered,
          placement,
          placeholder,
          popupStyle,
          popupClassName,
          dropdownClassName,
          disabled: customDisabled,
          status: customStatus,
          variant: customVariant,
          onCalendarChange,
          styles,
          classNames
        } = props,
        restProps = __rest(props, ["prefixCls", "getPopupContainer", "components", "style", "className", "rootClassName", "size", "bordered", "placement", "placeholder", "popupStyle", "popupClassName", "dropdownClassName", "disabled", "status", "variant", "onCalendarChange", "styles", "classNames"]);
      const {
        getPrefixCls,
        direction,
        getPopupContainer,
        // Consume different styles according to different names
        [consumerName]: consumerStyle
      } = (0, _react.useContext)(_configProvider.ConfigContext);
      const prefixCls = getPrefixCls('picker', customizePrefixCls);
      const {
        compactSize,
        compactItemClassnames
      } = (0, _Compact.useCompactItemContext)(prefixCls, direction);
      const innerRef = React.useRef(null);
      const [variant, enableVariantCls] = (0, _useVariants.default)('datePicker', customVariant, bordered);
      const rootCls = (0, _useCSSVarCls.default)(prefixCls);
      const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls, rootCls);
      (0, _react.useImperativeHandle)(ref, () => innerRef.current);
      const additionalProps = {
        showToday: true
      };
      const mergedPicker = picker || props.picker;
      const rootPrefixCls = getPrefixCls();
      // ==================== Legacy =====================
      const {
        onSelect,
        multiple
      } = restProps;
      const hasLegacyOnSelect = onSelect && picker === 'time' && !multiple;
      const onInternalCalendarChange = (date, dateStr, info) => {
        onCalendarChange === null || onCalendarChange === void 0 ? void 0 : onCalendarChange(date, dateStr, info);
        if (hasLegacyOnSelect) {
          onSelect(date);
        }
      };
      // =================== Warning =====================
      if (process.env.NODE_ENV !== 'production') {
        const warning = (0, _warning.devUseWarning)(displayName || 'DatePicker');
        process.env.NODE_ENV !== "production" ? warning(picker !== 'quarter', 'deprecated', `DatePicker.${displayName} is legacy usage. Please use DatePicker[picker='${picker}'] directly.`) : void 0;
        // ==================== Deprecated =====================
        const deprecatedProps = {
          dropdownClassName: 'classNames.popup.root',
          popupClassName: 'classNames.popup.root',
          popupStyle: 'styles.popup.root',
          bordered: 'variant',
          onSelect: 'onCalendarChange'
        };
        Object.entries(deprecatedProps).forEach(([oldProp, newProp]) => {
          warning.deprecated(!(oldProp in props), oldProp, newProp);
        });
      }
      const [mergedClassNames, mergedStyles] = (0, _useMergedPickerSemantic.default)(consumerName, classNames, styles, popupClassName || dropdownClassName, popupStyle);
      // ===================== Icon =====================
      const [mergedAllowClear, removeIcon] = (0, _util.useIcons)(props, prefixCls);
      // ================== components ==================
      const mergedComponents = (0, _useComponents.default)(components);
      // ===================== Size =====================
      const mergedSize = (0, _useSize.default)(ctx => {
        var _a;
        return (_a = customizeSize !== null && customizeSize !== void 0 ? customizeSize : compactSize) !== null && _a !== void 0 ? _a : ctx;
      });
      // ===================== Disabled =====================
      const disabled = React.useContext(_DisabledContext.default);
      const mergedDisabled = customDisabled !== null && customDisabled !== void 0 ? customDisabled : disabled;
      // ===================== FormItemInput =====================
      const formItemContext = (0, _react.useContext)(_context.FormItemInputContext);
      const {
        hasFeedback,
        status: contextStatus,
        feedbackIcon
      } = formItemContext;
      const suffixNode = /*#__PURE__*/React.createElement(React.Fragment, null, mergedPicker === 'time' ? /*#__PURE__*/React.createElement(_ClockCircleOutlined.default, null) : /*#__PURE__*/React.createElement(_CalendarOutlined.default, null), hasFeedback && feedbackIcon);
      const [contextLocale] = (0, _locale.useLocale)('DatePicker', _en_US.default);
      const locale = Object.assign(Object.assign({}, contextLocale), props.locale);
      // ============================ zIndex ============================
      const [zIndex] = (0, _useZIndex.useZIndex)('DatePicker', (_a = mergedStyles.popup.root) === null || _a === void 0 ? void 0 : _a.zIndex);
      return wrapCSSVar(/*#__PURE__*/React.createElement(_ContextIsolator.default, {
        space: true
      }, /*#__PURE__*/React.createElement(_rcPicker.default, Object.assign({
        ref: innerRef,
        placeholder: (0, _util.getPlaceholder)(locale, mergedPicker, placeholder),
        suffixIcon: suffixNode,
        placement: placement,
        prevIcon: /*#__PURE__*/React.createElement("span", {
          className: `${prefixCls}-prev-icon`
        }),
        nextIcon: /*#__PURE__*/React.createElement("span", {
          className: `${prefixCls}-next-icon`
        }),
        superPrevIcon: /*#__PURE__*/React.createElement("span", {
          className: `${prefixCls}-super-prev-icon`
        }),
        superNextIcon: /*#__PURE__*/React.createElement("span", {
          className: `${prefixCls}-super-next-icon`
        }),
        transitionName: `${rootPrefixCls}-slide-up`,
        picker: picker,
        onCalendarChange: onInternalCalendarChange
      }, additionalProps, restProps, {
        locale: locale.lang,
        className: (0, _classnames.default)({
          [`${prefixCls}-${mergedSize}`]: mergedSize,
          [`${prefixCls}-${variant}`]: enableVariantCls
        }, (0, _statusUtils.getStatusClassNames)(prefixCls, (0, _statusUtils.getMergedStatus)(contextStatus, customStatus), hasFeedback), hashId, compactItemClassnames, consumerStyle === null || consumerStyle === void 0 ? void 0 : consumerStyle.className, className, cssVarCls, rootCls, rootClassName, mergedClassNames.root),
        style: Object.assign(Object.assign(Object.assign({}, consumerStyle === null || consumerStyle === void 0 ? void 0 : consumerStyle.style), style), mergedStyles.root),
        prefixCls: prefixCls,
        getPopupContainer: customizeGetPopupContainer || getPopupContainer,
        generateConfig: generateConfig,
        components: mergedComponents,
        direction: direction,
        disabled: mergedDisabled,
        classNames: {
          popup: (0, _classnames.default)(hashId, cssVarCls, rootCls, rootClassName, mergedClassNames.popup.root)
        },
        styles: {
          popup: Object.assign(Object.assign({}, mergedStyles.popup.root), {
            zIndex
          })
        },
        allowClear: mergedAllowClear,
        removeIcon: removeIcon
      }))));
    });
    if (process.env.NODE_ENV !== 'production' && displayName) {
      Picker.displayName = displayName;
    }
    return Picker;
  };
  const DatePicker = getPicker();
  const WeekPicker = getPicker(_constant.WEEK, _constant.WEEKPICKER);
  const MonthPicker = getPicker(_constant.MONTH, _constant.MONTHPICKER);
  const YearPicker = getPicker(_constant.YEAR, _constant.YEARPICKER);
  const QuarterPicker = getPicker(_constant.QUARTER, _constant.QUARTERPICKER);
  const TimePicker = getPicker(_constant.TIME, _constant.TIMEPICKER);
  return {
    DatePicker,
    WeekPicker,
    MonthPicker,
    YearPicker,
    TimePicker,
    QuarterPicker
  };
};
var _default = exports.default = generatePicker;