"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = QRcodeStatus;
var _react = _interopRequireDefault(require("react"));
var _icons = require("@ant-design/icons");
var _button = _interopRequireDefault(require("../button"));
var _spin = _interopRequireDefault(require("../spin"));
const defaultSpin = /*#__PURE__*/_react.default.createElement(_spin.default, null);
function QRcodeStatus({
  prefixCls,
  locale,
  onRefresh,
  statusRender,
  status
}) {
  const defaultExpiredNode = /*#__PURE__*/_react.default.createElement(_react.default.Fragment, null, /*#__PURE__*/_react.default.createElement("p", {
    className: `${prefixCls}-expired`
  }, locale === null || locale === void 0 ? void 0 : locale.expired), onRefresh && (/*#__PURE__*/_react.default.createElement(_button.default, {
    type: "link",
    icon: /*#__PURE__*/_react.default.createElement(_icons.ReloadOutlined, null),
    onClick: onRefresh
  }, locale === null || locale === void 0 ? void 0 : locale.refresh)));
  const defaultScannedNode = /*#__PURE__*/_react.default.createElement("p", {
    className: `${prefixCls}-scanned`
  }, locale === null || locale === void 0 ? void 0 : locale.scanned);
  const defaultNodes = {
    expired: defaultExpiredNode,
    loading: defaultSpin,
    scanned: defaultScannedNode
  };
  const defaultStatusRender = info => defaultNodes[info.status];
  const mergedStatusRender = statusRender !== null && statusRender !== void 0 ? statusRender : defaultStatusRender;
  return mergedStatusRender({
    status,
    locale,
    onRefresh
  });
}