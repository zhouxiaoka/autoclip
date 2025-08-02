"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
var _typeof3 = require("@babel/runtime/helpers/typeof");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _objectWithoutProperties2 = _interopRequireDefault(require("@babel/runtime/helpers/objectWithoutProperties"));
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _typeof2 = _interopRequireDefault(require("@babel/runtime/helpers/typeof"));
var _classnames = _interopRequireDefault(require("classnames"));
var _useMergedState3 = _interopRequireDefault(require("rc-util/lib/hooks/useMergedState"));
var _omit = _interopRequireDefault(require("rc-util/lib/omit"));
var _ref2 = require("rc-util/lib/ref");
var React = _interopRequireWildcard(require("react"));
var _MotionThumb = _interopRequireDefault(require("./MotionThumb"));
var _excluded = ["prefixCls", "direction", "vertical", "options", "disabled", "defaultValue", "value", "name", "onChange", "className", "motionName"];
function _getRequireWildcardCache(e) { if ("function" != typeof WeakMap) return null; var r = new WeakMap(), t = new WeakMap(); return (_getRequireWildcardCache = function _getRequireWildcardCache(e) { return e ? t : r; })(e); }
function _interopRequireWildcard(e, r) { if (!r && e && e.__esModule) return e; if (null === e || "object" != _typeof3(e) && "function" != typeof e) return { default: e }; var t = _getRequireWildcardCache(r); if (t && t.has(e)) return t.get(e); var n = { __proto__: null }, a = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var u in e) if ("default" !== u && Object.prototype.hasOwnProperty.call(e, u)) { var i = a ? Object.getOwnPropertyDescriptor(e, u) : null; i && (i.get || i.set) ? Object.defineProperty(n, u, i) : n[u] = e[u]; } return n.default = e, t && t.set(e, n), n; }
function getValidTitle(option) {
  if (typeof option.title !== 'undefined') {
    return option.title;
  }

  // read `label` when title is `undefined`
  if ((0, _typeof2.default)(option.label) !== 'object') {
    var _option$label;
    return (_option$label = option.label) === null || _option$label === void 0 ? void 0 : _option$label.toString();
  }
}
function normalizeOptions(options) {
  return options.map(function (option) {
    if ((0, _typeof2.default)(option) === 'object' && option !== null) {
      var validTitle = getValidTitle(option);
      return (0, _objectSpread2.default)((0, _objectSpread2.default)({}, option), {}, {
        title: validTitle
      });
    }
    return {
      label: option === null || option === void 0 ? void 0 : option.toString(),
      title: option === null || option === void 0 ? void 0 : option.toString(),
      value: option
    };
  });
}
var InternalSegmentedOption = function InternalSegmentedOption(_ref) {
  var prefixCls = _ref.prefixCls,
    className = _ref.className,
    disabled = _ref.disabled,
    checked = _ref.checked,
    label = _ref.label,
    title = _ref.title,
    value = _ref.value,
    name = _ref.name,
    onChange = _ref.onChange,
    onFocus = _ref.onFocus,
    onBlur = _ref.onBlur,
    onKeyDown = _ref.onKeyDown,
    onKeyUp = _ref.onKeyUp,
    onMouseDown = _ref.onMouseDown;
  var handleChange = function handleChange(event) {
    if (disabled) {
      return;
    }
    onChange(event, value);
  };
  return /*#__PURE__*/React.createElement("label", {
    className: (0, _classnames.default)(className, (0, _defineProperty2.default)({}, "".concat(prefixCls, "-item-disabled"), disabled)),
    onMouseDown: onMouseDown
  }, /*#__PURE__*/React.createElement("input", {
    name: name,
    className: "".concat(prefixCls, "-item-input"),
    type: "radio",
    disabled: disabled,
    checked: checked,
    onChange: handleChange,
    onFocus: onFocus,
    onBlur: onBlur,
    onKeyDown: onKeyDown,
    onKeyUp: onKeyUp
  }), /*#__PURE__*/React.createElement("div", {
    className: "".concat(prefixCls, "-item-label"),
    title: title,
    "aria-selected": checked
  }, label));
};
var Segmented = /*#__PURE__*/React.forwardRef(function (props, ref) {
  var _segmentedOptions$, _classNames2;
  var _props$prefixCls = props.prefixCls,
    prefixCls = _props$prefixCls === void 0 ? 'rc-segmented' : _props$prefixCls,
    direction = props.direction,
    vertical = props.vertical,
    _props$options = props.options,
    options = _props$options === void 0 ? [] : _props$options,
    disabled = props.disabled,
    defaultValue = props.defaultValue,
    value = props.value,
    name = props.name,
    onChange = props.onChange,
    _props$className = props.className,
    className = _props$className === void 0 ? '' : _props$className,
    _props$motionName = props.motionName,
    motionName = _props$motionName === void 0 ? 'thumb-motion' : _props$motionName,
    restProps = (0, _objectWithoutProperties2.default)(props, _excluded);
  var containerRef = React.useRef(null);
  var mergedRef = React.useMemo(function () {
    return (0, _ref2.composeRef)(containerRef, ref);
  }, [containerRef, ref]);
  var segmentedOptions = React.useMemo(function () {
    return normalizeOptions(options);
  }, [options]);

  // Note: We should not auto switch value when value not exist in options
  // which may break single source of truth.
  var _useMergedState = (0, _useMergedState3.default)((_segmentedOptions$ = segmentedOptions[0]) === null || _segmentedOptions$ === void 0 ? void 0 : _segmentedOptions$.value, {
      value: value,
      defaultValue: defaultValue
    }),
    _useMergedState2 = (0, _slicedToArray2.default)(_useMergedState, 2),
    rawValue = _useMergedState2[0],
    setRawValue = _useMergedState2[1];

  // ======================= Change ========================
  var _React$useState = React.useState(false),
    _React$useState2 = (0, _slicedToArray2.default)(_React$useState, 2),
    thumbShow = _React$useState2[0],
    setThumbShow = _React$useState2[1];
  var handleChange = function handleChange(event, val) {
    setRawValue(val);
    onChange === null || onChange === void 0 || onChange(val);
  };
  var divProps = (0, _omit.default)(restProps, ['children']);

  // ======================= Focus ========================
  var _React$useState3 = React.useState(false),
    _React$useState4 = (0, _slicedToArray2.default)(_React$useState3, 2),
    isKeyboard = _React$useState4[0],
    setIsKeyboard = _React$useState4[1];
  var _React$useState5 = React.useState(false),
    _React$useState6 = (0, _slicedToArray2.default)(_React$useState5, 2),
    isFocused = _React$useState6[0],
    setIsFocused = _React$useState6[1];
  var handleFocus = function handleFocus() {
    setIsFocused(true);
  };
  var handleBlur = function handleBlur() {
    setIsFocused(false);
  };
  var handleMouseDown = function handleMouseDown() {
    setIsKeyboard(false);
  };

  // capture keyboard tab interaction for correct focus style
  var handleKeyUp = function handleKeyUp(event) {
    if (event.key === 'Tab') {
      setIsKeyboard(true);
    }
  };

  // ======================= Keyboard ========================
  var onOffset = function onOffset(offset) {
    var currentIndex = segmentedOptions.findIndex(function (option) {
      return option.value === rawValue;
    });
    var total = segmentedOptions.length;
    var nextIndex = (currentIndex + offset + total) % total;
    var nextOption = segmentedOptions[nextIndex];
    if (nextOption) {
      setRawValue(nextOption.value);
      onChange === null || onChange === void 0 || onChange(nextOption.value);
    }
  };
  var handleKeyDown = function handleKeyDown(event) {
    switch (event.key) {
      case 'ArrowLeft':
      case 'ArrowUp':
        onOffset(-1);
        break;
      case 'ArrowRight':
      case 'ArrowDown':
        onOffset(1);
        break;
    }
  };
  return /*#__PURE__*/React.createElement("div", (0, _extends2.default)({
    role: "radiogroup",
    "aria-label": "segmented control",
    tabIndex: disabled ? undefined : 0
  }, divProps, {
    className: (0, _classnames.default)(prefixCls, (_classNames2 = {}, (0, _defineProperty2.default)(_classNames2, "".concat(prefixCls, "-rtl"), direction === 'rtl'), (0, _defineProperty2.default)(_classNames2, "".concat(prefixCls, "-disabled"), disabled), (0, _defineProperty2.default)(_classNames2, "".concat(prefixCls, "-vertical"), vertical), _classNames2), className),
    ref: mergedRef
  }), /*#__PURE__*/React.createElement("div", {
    className: "".concat(prefixCls, "-group")
  }, /*#__PURE__*/React.createElement(_MotionThumb.default, {
    vertical: vertical,
    prefixCls: prefixCls,
    value: rawValue,
    containerRef: containerRef,
    motionName: "".concat(prefixCls, "-").concat(motionName),
    direction: direction,
    getValueIndex: function getValueIndex(val) {
      return segmentedOptions.findIndex(function (n) {
        return n.value === val;
      });
    },
    onMotionStart: function onMotionStart() {
      setThumbShow(true);
    },
    onMotionEnd: function onMotionEnd() {
      setThumbShow(false);
    }
  }), segmentedOptions.map(function (segmentedOption) {
    var _classNames3;
    return /*#__PURE__*/React.createElement(InternalSegmentedOption, (0, _extends2.default)({}, segmentedOption, {
      name: name,
      key: segmentedOption.value,
      prefixCls: prefixCls,
      className: (0, _classnames.default)(segmentedOption.className, "".concat(prefixCls, "-item"), (_classNames3 = {}, (0, _defineProperty2.default)(_classNames3, "".concat(prefixCls, "-item-selected"), segmentedOption.value === rawValue && !thumbShow), (0, _defineProperty2.default)(_classNames3, "".concat(prefixCls, "-item-focused"), isFocused && isKeyboard && segmentedOption.value === rawValue), _classNames3)),
      checked: segmentedOption.value === rawValue,
      onChange: handleChange,
      onFocus: handleFocus,
      onBlur: handleBlur,
      onKeyDown: handleKeyDown,
      onKeyUp: handleKeyUp,
      onMouseDown: handleMouseDown,
      disabled: !!disabled || !!segmentedOption.disabled
    }));
  })));
});
if (process.env.NODE_ENV !== 'production') {
  Segmented.displayName = 'Segmented';
}
var TypedSegmented = Segmented;
var _default = exports.default = TypedSegmented;