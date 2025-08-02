"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _KeyCode = _interopRequireDefault(require("rc-util/lib/KeyCode"));
var _react = _interopRequireDefault(require("react"));
var defaultPageSizeOptions = [10, 20, 50, 100];
var Options = function Options(props) {
  var _props$pageSizeOption = props.pageSizeOptions,
    pageSizeOptions = _props$pageSizeOption === void 0 ? defaultPageSizeOptions : _props$pageSizeOption,
    locale = props.locale,
    changeSize = props.changeSize,
    pageSize = props.pageSize,
    goButton = props.goButton,
    quickGo = props.quickGo,
    rootPrefixCls = props.rootPrefixCls,
    disabled = props.disabled,
    buildOptionText = props.buildOptionText,
    showSizeChanger = props.showSizeChanger,
    sizeChangerRender = props.sizeChangerRender;
  var _React$useState = _react.default.useState(''),
    _React$useState2 = (0, _slicedToArray2.default)(_React$useState, 2),
    goInputText = _React$useState2[0],
    setGoInputText = _React$useState2[1];
  var getValidValue = function getValidValue() {
    return !goInputText || Number.isNaN(goInputText) ? undefined : Number(goInputText);
  };
  var mergeBuildOptionText = typeof buildOptionText === 'function' ? buildOptionText : function (value) {
    return "".concat(value, " ").concat(locale.items_per_page);
  };
  var handleChange = function handleChange(e) {
    setGoInputText(e.target.value);
  };
  var handleBlur = function handleBlur(e) {
    if (goButton || goInputText === '') {
      return;
    }
    setGoInputText('');
    if (e.relatedTarget && (e.relatedTarget.className.indexOf("".concat(rootPrefixCls, "-item-link")) >= 0 || e.relatedTarget.className.indexOf("".concat(rootPrefixCls, "-item")) >= 0)) {
      return;
    }
    quickGo === null || quickGo === void 0 || quickGo(getValidValue());
  };
  var go = function go(e) {
    if (goInputText === '') {
      return;
    }
    if (e.keyCode === _KeyCode.default.ENTER || e.type === 'click') {
      setGoInputText('');
      quickGo === null || quickGo === void 0 || quickGo(getValidValue());
    }
  };
  var getPageSizeOptions = function getPageSizeOptions() {
    if (pageSizeOptions.some(function (option) {
      return option.toString() === pageSize.toString();
    })) {
      return pageSizeOptions;
    }
    return pageSizeOptions.concat([pageSize]).sort(function (a, b) {
      var numberA = Number.isNaN(Number(a)) ? 0 : Number(a);
      var numberB = Number.isNaN(Number(b)) ? 0 : Number(b);
      return numberA - numberB;
    });
  };
  // ============== cls ==============
  var prefixCls = "".concat(rootPrefixCls, "-options");

  // ============== render ==============

  if (!showSizeChanger && !quickGo) {
    return null;
  }
  var changeSelect = null;
  var goInput = null;
  var gotoButton = null;

  // >>>>> Size Changer
  if (showSizeChanger && sizeChangerRender) {
    changeSelect = sizeChangerRender({
      disabled: disabled,
      size: pageSize,
      onSizeChange: function onSizeChange(nextValue) {
        changeSize === null || changeSize === void 0 || changeSize(Number(nextValue));
      },
      'aria-label': locale.page_size,
      className: "".concat(prefixCls, "-size-changer"),
      options: getPageSizeOptions().map(function (opt) {
        return {
          label: mergeBuildOptionText(opt),
          value: opt
        };
      })
    });
  }

  // >>>>> Quick Go
  if (quickGo) {
    if (goButton) {
      gotoButton = typeof goButton === 'boolean' ? /*#__PURE__*/_react.default.createElement("button", {
        type: "button",
        onClick: go,
        onKeyUp: go,
        disabled: disabled,
        className: "".concat(prefixCls, "-quick-jumper-button")
      }, locale.jump_to_confirm) : /*#__PURE__*/_react.default.createElement("span", {
        onClick: go,
        onKeyUp: go
      }, goButton);
    }
    goInput = /*#__PURE__*/_react.default.createElement("div", {
      className: "".concat(prefixCls, "-quick-jumper")
    }, locale.jump_to, /*#__PURE__*/_react.default.createElement("input", {
      disabled: disabled,
      type: "text",
      value: goInputText,
      onChange: handleChange,
      onKeyUp: go,
      onBlur: handleBlur,
      "aria-label": locale.page
    }), locale.page, gotoButton);
  }
  return /*#__PURE__*/_react.default.createElement("li", {
    className: prefixCls
  }, changeSelect, goInput);
};
if (process.env.NODE_ENV !== 'production') {
  Options.displayName = 'Options';
}
var _default = exports.default = Options;