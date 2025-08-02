import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import _extends from "@babel/runtime/helpers/esm/extends";
import _defineProperty from "@babel/runtime/helpers/esm/defineProperty";
import _objectWithoutProperties from "@babel/runtime/helpers/esm/objectWithoutProperties";
var _excluded = ["showArrow", "headerClass", "isActive", "onItemClick", "forceRender", "className", "classNames", "styles", "prefixCls", "collapsible", "accordion", "panelKey", "extra", "header", "expandIcon", "openMotion", "destroyInactivePanel", "children"];
import classNames from 'classnames';
import CSSMotion from 'rc-motion';
import KeyCode from "rc-util/es/KeyCode";
import React from 'react';
import PanelContent from "./PanelContent";
var CollapsePanel = /*#__PURE__*/React.forwardRef(function (props, ref) {
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
    resetProps = _objectWithoutProperties(props, _excluded);
  var disabled = collapsible === 'disabled';
  var ifExtraExist = extra !== null && extra !== undefined && typeof extra !== 'boolean';
  var collapsibleProps = _defineProperty(_defineProperty(_defineProperty({
    onClick: function onClick() {
      onItemClick === null || onItemClick === void 0 || onItemClick(panelKey);
    },
    onKeyDown: function onKeyDown(e) {
      if (e.key === 'Enter' || e.keyCode === KeyCode.ENTER || e.which === KeyCode.ENTER) {
        onItemClick === null || onItemClick === void 0 || onItemClick(panelKey);
      }
    },
    role: accordion ? 'tab' : 'button'
  }, 'aria-expanded', isActive), 'aria-disabled', disabled), "tabIndex", disabled ? -1 : 0);

  // ======================== Icon ========================
  var iconNodeInner = typeof expandIcon === 'function' ? expandIcon(props) : /*#__PURE__*/React.createElement("i", {
    className: "arrow"
  });
  var iconNode = iconNodeInner && /*#__PURE__*/React.createElement("div", _extends({
    className: "".concat(prefixCls, "-expand-icon")
  }, ['header', 'icon'].includes(collapsible) ? collapsibleProps : {}), iconNodeInner);
  var collapsePanelClassNames = classNames("".concat(prefixCls, "-item"), _defineProperty(_defineProperty({}, "".concat(prefixCls, "-item-active"), isActive), "".concat(prefixCls, "-item-disabled"), disabled), className);
  var headerClassName = classNames(headerClass, "".concat(prefixCls, "-header"), _defineProperty({}, "".concat(prefixCls, "-collapsible-").concat(collapsible), !!collapsible), customizeClassNames.header);

  // ======================== HeaderProps ========================
  var headerProps = _objectSpread({
    className: headerClassName,
    style: styles.header
  }, ['header', 'icon'].includes(collapsible) ? {} : collapsibleProps);

  // ======================== Render ========================
  return /*#__PURE__*/React.createElement("div", _extends({}, resetProps, {
    ref: ref,
    className: collapsePanelClassNames
  }), /*#__PURE__*/React.createElement("div", headerProps, showArrow && iconNode, /*#__PURE__*/React.createElement("span", _extends({
    className: "".concat(prefixCls, "-header-text")
  }, collapsible === 'header' ? collapsibleProps : {}), header), ifExtraExist && /*#__PURE__*/React.createElement("div", {
    className: "".concat(prefixCls, "-extra")
  }, extra)), /*#__PURE__*/React.createElement(CSSMotion, _extends({
    visible: isActive,
    leavedClassName: "".concat(prefixCls, "-content-hidden")
  }, openMotion, {
    forceRender: forceRender,
    removeOnLeave: destroyInactivePanel
  }), function (_ref, motionRef) {
    var motionClassName = _ref.className,
      motionStyle = _ref.style;
    return /*#__PURE__*/React.createElement(PanelContent, {
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
export default CollapsePanel;