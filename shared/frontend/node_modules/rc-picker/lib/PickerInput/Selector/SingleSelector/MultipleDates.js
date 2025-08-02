"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = MultipleDates;
var _classnames = _interopRequireDefault(require("classnames"));
var _rcOverflow = _interopRequireDefault(require("rc-overflow"));
var React = _interopRequireWildcard(require("react"));
function MultipleDates(props) {
  var prefixCls = props.prefixCls,
    value = props.value,
    onRemove = props.onRemove,
    _props$removeIcon = props.removeIcon,
    removeIcon = _props$removeIcon === void 0 ? '×' : _props$removeIcon,
    formatDate = props.formatDate,
    disabled = props.disabled,
    maxTagCount = props.maxTagCount,
    placeholder = props.placeholder;
  var selectorCls = "".concat(prefixCls, "-selector");
  var selectionCls = "".concat(prefixCls, "-selection");
  var overflowCls = "".concat(selectionCls, "-overflow");

  // ========================= Item =========================
  function renderSelector(content, onClose) {
    return /*#__PURE__*/React.createElement("span", {
      className: (0, _classnames.default)("".concat(selectionCls, "-item")),
      title: typeof content === 'string' ? content : null
    }, /*#__PURE__*/React.createElement("span", {
      className: "".concat(selectionCls, "-item-content")
    }, content), !disabled && onClose && /*#__PURE__*/React.createElement("span", {
      onMouseDown: function onMouseDown(e) {
        e.preventDefault();
      },
      onClick: onClose,
      className: "".concat(selectionCls, "-item-remove")
    }, removeIcon));
  }
  function renderItem(date) {
    var displayLabel = formatDate(date);
    var onClose = function onClose(event) {
      if (event) event.stopPropagation();
      onRemove(date);
    };
    return renderSelector(displayLabel, onClose);
  }

  // ========================= Rest =========================
  function renderRest(omittedValues) {
    var content = "+ ".concat(omittedValues.length, " ...");
    return renderSelector(content);
  }

  // ======================== Render ========================

  return /*#__PURE__*/React.createElement("div", {
    className: selectorCls
  }, /*#__PURE__*/React.createElement(_rcOverflow.default, {
    prefixCls: overflowCls,
    data: value,
    renderItem: renderItem,
    renderRest: renderRest
    // suffix={inputNode}
    ,
    itemKey: function itemKey(date) {
      return formatDate(date);
    },
    maxCount: maxTagCount
  }), !value.length && /*#__PURE__*/React.createElement("span", {
    className: "".concat(prefixCls, "-selection-placeholder")
  }, placeholder));
}