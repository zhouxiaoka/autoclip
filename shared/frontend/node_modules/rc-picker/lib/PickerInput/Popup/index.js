"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = Popup;
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcResizeObserver = _interopRequireDefault(require("rc-resize-observer"));
var React = _interopRequireWildcard(require("react"));
var _miscUtil = require("../../utils/miscUtil");
var _context = _interopRequireDefault(require("../context"));
var _Footer = _interopRequireDefault(require("./Footer"));
var _PopupPanel = _interopRequireDefault(require("./PopupPanel"));
var _PresetPanel = _interopRequireDefault(require("./PresetPanel"));
function Popup(props) {
  var panelRender = props.panelRender,
    internalMode = props.internalMode,
    picker = props.picker,
    showNow = props.showNow,
    range = props.range,
    multiple = props.multiple,
    _props$activeInfo = props.activeInfo,
    activeInfo = _props$activeInfo === void 0 ? [0, 0, 0] : _props$activeInfo,
    presets = props.presets,
    onPresetHover = props.onPresetHover,
    onPresetSubmit = props.onPresetSubmit,
    onFocus = props.onFocus,
    onBlur = props.onBlur,
    onPanelMouseDown = props.onPanelMouseDown,
    direction = props.direction,
    value = props.value,
    onSelect = props.onSelect,
    isInvalid = props.isInvalid,
    defaultOpenValue = props.defaultOpenValue,
    onOk = props.onOk,
    onSubmit = props.onSubmit;
  var _React$useContext = React.useContext(_context.default),
    prefixCls = _React$useContext.prefixCls;
  var panelPrefixCls = "".concat(prefixCls, "-panel");
  var rtl = direction === 'rtl';

  // ========================= Refs =========================
  var arrowRef = React.useRef(null);
  var wrapperRef = React.useRef(null);

  // ======================== Offset ========================
  var _React$useState = React.useState(0),
    _React$useState2 = (0, _slicedToArray2.default)(_React$useState, 2),
    containerWidth = _React$useState2[0],
    setContainerWidth = _React$useState2[1];
  var _React$useState3 = React.useState(0),
    _React$useState4 = (0, _slicedToArray2.default)(_React$useState3, 2),
    containerOffset = _React$useState4[0],
    setContainerOffset = _React$useState4[1];
  var _React$useState5 = React.useState(0),
    _React$useState6 = (0, _slicedToArray2.default)(_React$useState5, 2),
    arrowOffset = _React$useState6[0],
    setArrowOffset = _React$useState6[1];
  var onResize = function onResize(info) {
    if (info.width) {
      setContainerWidth(info.width);
    }
  };
  var _activeInfo = (0, _slicedToArray2.default)(activeInfo, 3),
    activeInputLeft = _activeInfo[0],
    activeInputRight = _activeInfo[1],
    selectorWidth = _activeInfo[2];
  var _React$useState7 = React.useState(0),
    _React$useState8 = (0, _slicedToArray2.default)(_React$useState7, 2),
    retryTimes = _React$useState8[0],
    setRetryTimes = _React$useState8[1];
  React.useEffect(function () {
    setRetryTimes(10);
  }, [activeInputLeft]);
  React.useEffect(function () {
    // `activeOffset` is always align with the active input element
    // So we need only check container contains the `activeOffset`
    if (range && wrapperRef.current) {
      var _arrowRef$current;
      // Offset in case container has border radius
      var arrowWidth = ((_arrowRef$current = arrowRef.current) === null || _arrowRef$current === void 0 ? void 0 : _arrowRef$current.offsetWidth) || 0;

      // Arrow Offset
      var wrapperRect = wrapperRef.current.getBoundingClientRect();
      if (!wrapperRect.height || wrapperRect.right < 0) {
        setRetryTimes(function (times) {
          return Math.max(0, times - 1);
        });
        return;
      }
      var nextArrowOffset = (rtl ? activeInputRight - arrowWidth : activeInputLeft) - wrapperRect.left;
      setArrowOffset(nextArrowOffset);

      // Container Offset
      if (containerWidth && containerWidth < selectorWidth) {
        var offset = rtl ? wrapperRect.right - (activeInputRight - arrowWidth + containerWidth) : activeInputLeft + arrowWidth - wrapperRect.left - containerWidth;
        var safeOffset = Math.max(0, offset);
        setContainerOffset(safeOffset);
      } else {
        setContainerOffset(0);
      }
    }
  }, [retryTimes, rtl, containerWidth, activeInputLeft, activeInputRight, selectorWidth, range]);

  // ======================== Custom ========================
  function filterEmpty(list) {
    return list.filter(function (item) {
      return item;
    });
  }
  var valueList = React.useMemo(function () {
    return filterEmpty((0, _miscUtil.toArray)(value));
  }, [value]);
  var isTimePickerEmptyValue = picker === 'time' && !valueList.length;
  var footerSubmitValue = React.useMemo(function () {
    if (isTimePickerEmptyValue) {
      return filterEmpty([defaultOpenValue]);
    }
    return valueList;
  }, [isTimePickerEmptyValue, valueList, defaultOpenValue]);
  var popupPanelValue = isTimePickerEmptyValue ? defaultOpenValue : valueList;
  var disableSubmit = React.useMemo(function () {
    // Empty is invalid
    if (!footerSubmitValue.length) {
      return true;
    }
    return footerSubmitValue.some(function (val) {
      return isInvalid(val);
    });
  }, [footerSubmitValue, isInvalid]);
  var onFooterSubmit = function onFooterSubmit() {
    // For TimePicker, we will additional trigger the value update
    if (isTimePickerEmptyValue) {
      onSelect(defaultOpenValue);
    }
    onOk();
    onSubmit();
  };
  var mergedNodes = /*#__PURE__*/React.createElement("div", {
    className: "".concat(prefixCls, "-panel-layout")
  }, /*#__PURE__*/React.createElement(_PresetPanel.default, {
    prefixCls: prefixCls,
    presets: presets,
    onClick: onPresetSubmit,
    onHover: onPresetHover
  }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(_PopupPanel.default, (0, _extends2.default)({}, props, {
    value: popupPanelValue
  })), /*#__PURE__*/React.createElement(_Footer.default, (0, _extends2.default)({}, props, {
    showNow: multiple ? false : showNow,
    invalid: disableSubmit,
    onSubmit: onFooterSubmit
  }))));
  if (panelRender) {
    mergedNodes = panelRender(mergedNodes);
  }

  // ======================== Render ========================
  var containerPrefixCls = "".concat(panelPrefixCls, "-container");
  var marginLeft = 'marginLeft';
  var marginRight = 'marginRight';

  // Container
  var renderNode = /*#__PURE__*/React.createElement("div", {
    onMouseDown: onPanelMouseDown,
    tabIndex: -1,
    className: (0, _classnames.default)(containerPrefixCls, // Used for Today Button style, safe to remove if no need
    "".concat(prefixCls, "-").concat(internalMode, "-panel-container")),
    style: (0, _defineProperty2.default)((0, _defineProperty2.default)({}, rtl ? marginRight : marginLeft, containerOffset), rtl ? marginLeft : marginRight, 'auto')
    // Still wish not to lose focus on mouse down
    // onMouseDown={(e) => {
    //   // e.preventDefault();
    // }}
    ,
    onFocus: onFocus,
    onBlur: onBlur
  }, mergedNodes);
  if (range) {
    renderNode = /*#__PURE__*/React.createElement("div", {
      onMouseDown: onPanelMouseDown,
      ref: wrapperRef,
      className: (0, _classnames.default)("".concat(prefixCls, "-range-wrapper"), "".concat(prefixCls, "-").concat(picker, "-range-wrapper"))
    }, /*#__PURE__*/React.createElement("div", {
      ref: arrowRef,
      className: "".concat(prefixCls, "-range-arrow"),
      style: {
        left: arrowOffset
      }
    }), /*#__PURE__*/React.createElement(_rcResizeObserver.default, {
      onResize: onResize
    }, renderNode));
  }
  return renderNode;
}