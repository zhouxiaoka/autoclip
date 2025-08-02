"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _CheckOutlined = _interopRequireDefault(require("@ant-design/icons/CheckOutlined"));
var _CopyOutlined = _interopRequireDefault(require("@ant-design/icons/CopyOutlined"));
var _LoadingOutlined = _interopRequireDefault(require("@ant-design/icons/LoadingOutlined"));
var _classnames = _interopRequireDefault(require("classnames"));
var _tooltip = _interopRequireDefault(require("../../tooltip"));
var _util = require("./util");
const CopyBtn = ({
  prefixCls,
  copied,
  locale,
  iconOnly,
  tooltips,
  icon,
  tabIndex,
  onCopy,
  loading: btnLoading
}) => {
  const tooltipNodes = (0, _util.toList)(tooltips);
  const iconNodes = (0, _util.toList)(icon);
  const {
    copied: copiedText,
    copy: copyText
  } = locale !== null && locale !== void 0 ? locale : {};
  const systemStr = copied ? copiedText : copyText;
  const copyTitle = (0, _util.getNode)(tooltipNodes[copied ? 1 : 0], systemStr);
  const ariaLabel = typeof copyTitle === 'string' ? copyTitle : systemStr;
  return /*#__PURE__*/React.createElement(_tooltip.default, {
    title: copyTitle
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: (0, _classnames.default)(`${prefixCls}-copy`, {
      [`${prefixCls}-copy-success`]: copied,
      [`${prefixCls}-copy-icon-only`]: iconOnly
    }),
    onClick: onCopy,
    "aria-label": ariaLabel,
    tabIndex: tabIndex
  }, copied ? (0, _util.getNode)(iconNodes[1], /*#__PURE__*/React.createElement(_CheckOutlined.default, null), true) : (0, _util.getNode)(iconNodes[0], btnLoading ? /*#__PURE__*/React.createElement(_LoadingOutlined.default, null) : /*#__PURE__*/React.createElement(_CopyOutlined.default, null), true)));
};
var _default = exports.default = CopyBtn;