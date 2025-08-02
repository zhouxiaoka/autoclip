"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = Footer;
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _classnames = _interopRequireDefault(require("classnames"));
var React = _interopRequireWildcard(require("react"));
var _useTimeInfo3 = _interopRequireDefault(require("../../hooks/useTimeInfo"));
var _context = _interopRequireDefault(require("../context"));
function Footer(props) {
  var mode = props.mode,
    internalMode = props.internalMode,
    renderExtraFooter = props.renderExtraFooter,
    showNow = props.showNow,
    showTime = props.showTime,
    onSubmit = props.onSubmit,
    onNow = props.onNow,
    invalid = props.invalid,
    needConfirm = props.needConfirm,
    generateConfig = props.generateConfig,
    disabledDate = props.disabledDate;
  var _React$useContext = React.useContext(_context.default),
    prefixCls = _React$useContext.prefixCls,
    locale = _React$useContext.locale,
    _React$useContext$but = _React$useContext.button,
    Button = _React$useContext$but === void 0 ? 'button' : _React$useContext$but;

  // >>> Now
  var now = generateConfig.getNow();
  var _useTimeInfo = (0, _useTimeInfo3.default)(generateConfig, showTime, now),
    _useTimeInfo2 = (0, _slicedToArray2.default)(_useTimeInfo, 1),
    getValidTime = _useTimeInfo2[0];

  // ======================== Extra =========================
  var extraNode = renderExtraFooter === null || renderExtraFooter === void 0 ? void 0 : renderExtraFooter(mode);

  // ======================== Ranges ========================
  var nowDisabled = disabledDate(now, {
    type: mode
  });
  var onInternalNow = function onInternalNow() {
    if (!nowDisabled) {
      var validateNow = getValidTime(now);
      onNow(validateNow);
    }
  };
  var nowPrefixCls = "".concat(prefixCls, "-now");
  var nowBtnPrefixCls = "".concat(nowPrefixCls, "-btn");
  var presetNode = showNow && /*#__PURE__*/React.createElement("li", {
    className: nowPrefixCls
  }, /*#__PURE__*/React.createElement("a", {
    className: (0, _classnames.default)(nowBtnPrefixCls, nowDisabled && "".concat(nowBtnPrefixCls, "-disabled")),
    "aria-disabled": nowDisabled,
    onClick: onInternalNow
  }, internalMode === 'date' ? locale.today : locale.now));

  // >>> OK
  var okNode = needConfirm && /*#__PURE__*/React.createElement("li", {
    className: "".concat(prefixCls, "-ok")
  }, /*#__PURE__*/React.createElement(Button, {
    disabled: invalid,
    onClick: onSubmit
  }, locale.ok));
  var rangeNode = (presetNode || okNode) && /*#__PURE__*/React.createElement("ul", {
    className: "".concat(prefixCls, "-ranges")
  }, presetNode, okNode);

  // ======================== Render ========================
  if (!extraNode && !rangeNode) {
    return null;
  }
  return /*#__PURE__*/React.createElement("div", {
    className: "".concat(prefixCls, "-footer")
  }, extraNode && /*#__PURE__*/React.createElement("div", {
    className: "".concat(prefixCls, "-footer-extra")
  }, extraNode), rangeNode);
}