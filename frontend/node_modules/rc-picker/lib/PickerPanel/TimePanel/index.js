"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = TimePanel;
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _classnames = _interopRequireDefault(require("classnames"));
var React = _interopRequireWildcard(require("react"));
var _dateUtil = require("../../utils/dateUtil");
var _context = require("../context");
var _PanelHeader = _interopRequireDefault(require("../PanelHeader"));
var _TimePanelBody = _interopRequireDefault(require("./TimePanelBody"));
function TimePanel(props) {
  var prefixCls = props.prefixCls,
    value = props.value,
    locale = props.locale,
    generateConfig = props.generateConfig,
    showTime = props.showTime;
  var _ref = showTime || {},
    format = _ref.format;
  var panelPrefixCls = "".concat(prefixCls, "-time-panel");

  // ========================== Base ==========================
  var _useInfo = (0, _context.useInfo)(props, 'time'),
    _useInfo2 = (0, _slicedToArray2.default)(_useInfo, 1),
    info = _useInfo2[0];

  // ========================= Render =========================
  return /*#__PURE__*/React.createElement(_context.PanelContext.Provider, {
    value: info
  }, /*#__PURE__*/React.createElement("div", {
    className: (0, _classnames.default)(panelPrefixCls)
  }, /*#__PURE__*/React.createElement(_PanelHeader.default, null, value ? (0, _dateUtil.formatValue)(value, {
    locale: locale,
    format: format,
    generateConfig: generateConfig
  }) : "\xA0"), /*#__PURE__*/React.createElement(_TimePanelBody.default, showTime)));
}