"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _objectWithoutProperties2 = _interopRequireDefault(require("@babel/runtime/helpers/objectWithoutProperties"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcMotion = _interopRequireDefault(require("rc-motion"));
var _KeyCode = _interopRequireDefault(require("rc-util/lib/KeyCode"));
var _react = _interopRequireDefault(require("react"));
var _PanelContent = _interopRequireDefault(require("./PanelContent"));
var _excluded = ["showArrow", "headerClass", "isActive", "onItemClick", "forceRender", "className", "classNames", "styles", "prefixCls", "collapsible", "accordion", "panelKey", "extra", "header", "expandIcon", "openMotion", "destroyInactivePanel", "children"];
var CollapsePanel = /*#__PURE__*/_react.default.forwardRef(function (props, ref) {
  var _props$showArrow = props.showArrow,
    showArrow = _props$showArrow === void 0 ? true : _props$showArrow,
    headerClass = props.headerClass,
    isActive = props.isActive,
    onItemClick = props.onItemClick,
    forceRender = props.forceRender,
    className = props.className,
    _props$classNames = props.classNames,
    customizeClassNames = _props$classNames === void 0 ? {} : _props$classNames,
    _props$styles = props.styles,
    styles = _props$styles === void 0 ? {} : _props$styles,
    prefixCls = props.prefixCls,
    collapsible = props.collapsible,
    accordion = props.accordion,
    panelKey = props.panelKey,
    extra = props.extra,
    header = props.header,
    expandIcon = props.expandIcon,
    openMotion = props.openMotion,
    destroyInactivePanel = props.destroyInactivePanel,
    children = props.children,
    resetProps = (0, _objectWithoutProperties2.default)(props, _excluded);
  var disabled = collapsible === 'disabled';
  var ifExtraExist = extra !== null && extra !== undefined && typeof extra !== 'boolean';
  var collapsibleProps = (0, _defineProperty2.default)((0, _defineProperty2.default)((0, _defineProperty2.default)({
    onClick: function onClick() {
      onItemClick === null || onItemClick === void 0 || onItemClick(panelKey);
    },
    onKeyDown: function onKeyDown(e) {
      if (e.key === 'Enter' || e.keyCode === _KeyCode.default.ENTER || e.which === _KeyCode.default.ENTER) {
        onItemClick === null || onItemClick === void 0 || onItemClick(panelKey);
      }
    },
    role: accordion ? 'tab' : 'button'
  }, 'aria-expanded', isActive), 'aria-disabled', disabled), "tabIndex", disabled ? -1 : 0);

  // ======================== Icon ========================
  var iconNodeInner = typeof expandIcon === 'function' ? expandIcon(props) : /*#__PURE__*/_react.default.createElement("i", {
    className: "arrow"
  });
  var iconNode = iconNodeInner && /*#__PURE__*/_react.default.createElement("div", (0, _extends2.default)({
    className: "".concat(prefixCls, "-expand-icon")
  }, ['header', 'icon'].includes(collapsible) ? collapsibleProps : {}), iconNodeInner);
  var collapsePanelClassNames = (0, _classnames.default)("".concat(prefixCls, "-item"), (0, _defineProperty2.default)((0, _defineProperty2.default)({}, "".concat(prefixCls, "-item-active"), isActive), "".concat(prefixCls, "-item-disabled"), disabled), className);
  var headerClassName = (0, _classnames.default)(headerClass, "".concat(prefixCls, "-header"), (0, _defineProperty2.default)({}, "".concat(prefixCls, "-collapsible-").concat(collapsible), !!collapsible), customizeClassNames.header);

  // ======================== HeaderProps ========================
  var headerProps = (0, _objectSpread2.default)({
    className: headerClassName,
    style: styles.header
  }, ['header', 'icon'].includes(collapsible) ? {} : collapsibleProps);

  // ======================== Render ========================
  return /*#__PURE__*/_react.default.createElement("div", (0, _extends2.default)({}, resetProps, {
    ref: ref,
    className: collapsePanelClassNames
  }), /*#__PURE__*/_react.default.createElement("div", headerProps, showArrow && iconNode, /*#__PURE__*/_react.default.createElement("span", (0, _extends2.default)({
    className: "".concat(prefixCls, "-header-text")
  }, collapsible === 'header' ? collapsibleProps : {}), header), ifExtraExist && /*#__PURE__*/_react.default.createElement("div", {
    className: "".concat(prefixCls, "-extra")
  }, extra)), /*#__PURE__*/_react.default.createElement(_rcMotion.default, (0, _extends2.default)({
    visible: isActive,
    leavedClassName: "".concat(prefixCls, "-content-hidden")
  }, openMotion, {
    forceRender: forceRender,
    removeOnLeave: destroyInactivePanel
  }), function (_ref, motionRef) {
    var motionClassName = _ref.className,
      motionStyle = _ref.style;
    return /*#__PURE__*/_react.default.createElement(_PanelContent.default, {
      ref: motionRef,
      prefixCls: prefixCls,
      className: motionClassName,
      classNames: customizeClassNames,
      style: motionStyle,
      styles: styles,
      isActive: isActive,
      forceRender: forceRender,
      role: accordion ? 'tabpanel' : void 0
    }, children);
  }));
});
var _default = exports.default = CollapsePanel;