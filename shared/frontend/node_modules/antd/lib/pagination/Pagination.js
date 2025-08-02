"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _DoubleLeftOutlined = _interopRequireDefault(require("@ant-design/icons/DoubleLeftOutlined"));
var _DoubleRightOutlined = _interopRequireDefault(require("@ant-design/icons/DoubleRightOutlined"));
var _LeftOutlined = _interopRequireDefault(require("@ant-design/icons/LeftOutlined"));
var _RightOutlined = _interopRequireDefault(require("@ant-design/icons/RightOutlined"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcPagination = _interopRequireDefault(require("rc-pagination"));
var _en_US = _interopRequireDefault(require("rc-pagination/lib/locale/en_US"));
var _warning = require("../_util/warning");
var _context = require("../config-provider/context");
var _useSize = _interopRequireDefault(require("../config-provider/hooks/useSize"));
var _useBreakpoint = _interopRequireDefault(require("../grid/hooks/useBreakpoint"));
var _locale = require("../locale");
var _select = _interopRequireDefault(require("../select"));
var _internal = require("../theme/internal");
var _style = _interopRequireDefault(require("./style"));
var _bordered = _interopRequireDefault(require("./style/bordered"));
var _useShowSizeChanger = _interopRequireDefault(require("./useShowSizeChanger"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const Pagination = props => {
  const {
      align,
      prefixCls: customizePrefixCls,
      selectPrefixCls: customizeSelectPrefixCls,
      className,
      rootClassName,
      style,
      size: customizeSize,
      locale: customLocale,
      responsive,
      showSizeChanger,
      selectComponentClass,
      pageSizeOptions
    } = props,
    restProps = __rest(props, ["align", "prefixCls", "selectPrefixCls", "className", "rootClassName", "style", "size", "locale", "responsive", "showSizeChanger", "selectComponentClass", "pageSizeOptions"]);
  const {
    xs
  } = (0, _useBreakpoint.default)(responsive);
  const [, token] = (0, _internal.useToken)();
  const {
    getPrefixCls,
    direction,
    showSizeChanger: contextShowSizeChangerConfig,
    className: contextClassName,
    style: contextStyle
  } = (0, _context.useComponentConfig)('pagination');
  const prefixCls = getPrefixCls('pagination', customizePrefixCls);
  // Style
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls);
  // ============================== Size ==============================
  const mergedSize = (0, _useSize.default)(customizeSize);
  const isSmall = mergedSize === 'small' || !!(xs && !mergedSize && responsive);
  // ============================= Locale =============================
  const [contextLocale] = (0, _locale.useLocale)('Pagination', _en_US.default);
  const locale = Object.assign(Object.assign({}, contextLocale), customLocale);
  // ========================== Size Changer ==========================
  // Merge the props showSizeChanger
  const [propShowSizeChanger, propSizeChangerSelectProps] = (0, _useShowSizeChanger.default)(showSizeChanger);
  const [contextShowSizeChanger, contextSizeChangerSelectProps] = (0, _useShowSizeChanger.default)(contextShowSizeChangerConfig);
  const mergedShowSizeChanger = propShowSizeChanger !== null && propShowSizeChanger !== void 0 ? propShowSizeChanger : contextShowSizeChanger;
  const mergedShowSizeChangerSelectProps = propSizeChangerSelectProps !== null && propSizeChangerSelectProps !== void 0 ? propSizeChangerSelectProps : contextSizeChangerSelectProps;
  const SizeChanger = selectComponentClass || _select.default;
  // Generate options
  const mergedPageSizeOptions = React.useMemo(() => {
    return pageSizeOptions ? pageSizeOptions.map(option => Number(option)) : undefined;
  }, [pageSizeOptions]);
  // Render size changer
  const sizeChangerRender = info => {
    var _a;
    const {
      disabled,
      size: pageSize,
      onSizeChange,
      'aria-label': ariaLabel,
      className: sizeChangerClassName,
      options
    } = info;
    const {
      className: propSizeChangerClassName,
      onChange: propSizeChangerOnChange
    } = mergedShowSizeChangerSelectProps || {};
    // Origin Select is using Select.Option,
    // So it make the option value must be string
    // Just for compatible
    const selectedValue = (_a = options.find(option => String(option.value) === String(pageSize))) === null || _a === void 0 ? void 0 : _a.value;
    return /*#__PURE__*/React.createElement(SizeChanger, Object.assign({
      disabled: disabled,
      showSearch: true,
      popupMatchSelectWidth: false,
      getPopupContainer: triggerNode => triggerNode.parentNode,
      "aria-label": ariaLabel,
      options: options
    }, mergedShowSizeChangerSelectProps, {
      value: selectedValue,
      onChange: (nextSize, option) => {
        onSizeChange === null || onSizeChange === void 0 ? void 0 : onSizeChange(nextSize);
        propSizeChangerOnChange === null || propSizeChangerOnChange === void 0 ? void 0 : propSizeChangerOnChange(nextSize, option);
      },
      size: isSmall ? 'small' : 'middle',
      className: (0, _classnames.default)(sizeChangerClassName, propSizeChangerClassName)
    }));
  };
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('Pagination');
    process.env.NODE_ENV !== "production" ? warning(!selectComponentClass, 'usage', '`selectComponentClass` is not official api which will be removed.') : void 0;
  }
  // ============================= Render =============================
  const iconsProps = React.useMemo(() => {
    const ellipsis = /*#__PURE__*/React.createElement("span", {
      className: `${prefixCls}-item-ellipsis`
    }, "\u2022\u2022\u2022");
    const prevIcon = /*#__PURE__*/React.createElement("button", {
      className: `${prefixCls}-item-link`,
      type: "button",
      tabIndex: -1
    }, direction === 'rtl' ? /*#__PURE__*/React.createElement(_RightOutlined.default, null) : /*#__PURE__*/React.createElement(_LeftOutlined.default, null));
    const nextIcon = /*#__PURE__*/React.createElement("button", {
      className: `${prefixCls}-item-link`,
      type: "button",
      tabIndex: -1
    }, direction === 'rtl' ? /*#__PURE__*/React.createElement(_LeftOutlined.default, null) : /*#__PURE__*/React.createElement(_RightOutlined.default, null));
    const jumpPrevIcon =
    /*#__PURE__*/
    // biome-ignore lint/a11y/useValidAnchor: it is hard to refactor
    React.createElement("a", {
      className: `${prefixCls}-item-link`
    }, /*#__PURE__*/React.createElement("div", {
      className: `${prefixCls}-item-container`
    }, direction === 'rtl' ? (/*#__PURE__*/React.createElement(_DoubleRightOutlined.default, {
      className: `${prefixCls}-item-link-icon`
    })) : (/*#__PURE__*/React.createElement(_DoubleLeftOutlined.default, {
      className: `${prefixCls}-item-link-icon`
    })), ellipsis));
    const jumpNextIcon =
    /*#__PURE__*/
    // biome-ignore lint/a11y/useValidAnchor: it is hard to refactor
    React.createElement("a", {
      className: `${prefixCls}-item-link`
    }, /*#__PURE__*/React.createElement("div", {
      className: `${prefixCls}-item-container`
    }, direction === 'rtl' ? (/*#__PURE__*/React.createElement(_DoubleLeftOutlined.default, {
      className: `${prefixCls}-item-link-icon`
    })) : (/*#__PURE__*/React.createElement(_DoubleRightOutlined.default, {
      className: `${prefixCls}-item-link-icon`
    })), ellipsis));
    return {
      prevIcon,
      nextIcon,
      jumpPrevIcon,
      jumpNextIcon
    };
  }, [direction, prefixCls]);
  const selectPrefixCls = getPrefixCls('select', customizeSelectPrefixCls);
  const extendedClassName = (0, _classnames.default)({
    [`${prefixCls}-${align}`]: !!align,
    [`${prefixCls}-mini`]: isSmall,
    [`${prefixCls}-rtl`]: direction === 'rtl',
    [`${prefixCls}-bordered`]: token.wireframe
  }, contextClassName, className, rootClassName, hashId, cssVarCls);
  const mergedStyle = Object.assign(Object.assign({}, contextStyle), style);
  return wrapCSSVar(/*#__PURE__*/React.createElement(React.Fragment, null, token.wireframe && /*#__PURE__*/React.createElement(_bordered.default, {
    prefixCls: prefixCls
  }), /*#__PURE__*/React.createElement(_rcPagination.default, Object.assign({}, iconsProps, restProps, {
    style: mergedStyle,
    prefixCls: prefixCls,
    selectPrefixCls: selectPrefixCls,
    className: extendedClassName,
    locale: locale,
    pageSizeOptions: mergedPageSizeOptions,
    showSizeChanger: mergedShowSizeChanger,
    sizeChangerRender: sizeChangerRender
  }))));
};
if (process.env.NODE_ENV !== 'production') {
  Pagination.displayName = 'Pagination';
}
var _default = exports.default = Pagination;