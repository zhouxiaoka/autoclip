"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
var _typeof = require("@babel/runtime/helpers/typeof");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _objectWithoutProperties2 = _interopRequireDefault(require("@babel/runtime/helpers/objectWithoutProperties"));
var _trigger = _interopRequireDefault(require("@rc-component/trigger"));
var _classnames = _interopRequireDefault(require("classnames"));
var _react = _interopRequireWildcard(require("react"));
var React = _react;
var _placements = require("./placements");
var _Popup = _interopRequireDefault(require("./Popup"));
var _useId = _interopRequireDefault(require("rc-util/lib/hooks/useId"));
var _excluded = ["overlayClassName", "trigger", "mouseEnterDelay", "mouseLeaveDelay", "overlayStyle", "prefixCls", "children", "onVisibleChange", "afterVisibleChange", "transitionName", "animation", "motion", "placement", "align", "destroyTooltipOnHide", "defaultVisible", "getTooltipContainer", "overlayInnerStyle", "arrowContent", "overlay", "id", "showArrow", "classNames", "styles"];
function _getRequireWildcardCache(e) { if ("function" != typeof WeakMap) return null; var r = new WeakMap(), t = new WeakMap(); return (_getRequireWildcardCache = function _getRequireWildcardCache(e) { return e ? t : r; })(e); }
function _interopRequireWildcard(e, r) { if (!r && e && e.__esModule) return e; if (null === e || "object" != _typeof(e) && "function" != typeof e) return { default: e }; var t = _getRequireWildcardCache(r); if (t && t.has(e)) return t.get(e); var n = { __proto__: null }, a = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var u in e) if ("default" !== u && Object.prototype.hasOwnProperty.call(e, u)) { var i = a ? Object.getOwnPropertyDescriptor(e, u) : null; i && (i.get || i.set) ? Object.defineProperty(n, u, i) : n[u] = e[u]; } return n.default = e, t && t.set(e, n), n; }
var Tooltip = function Tooltip(props, ref) {
  var overlayClassName = props.overlayClassName,
    _props$trigger = props.trigger,
    trigger = _props$trigger === void 0 ? ['hover'] : _props$trigger,
    _props$mouseEnterDela = props.mouseEnterDelay,
    mouseEnterDelay = _props$mouseEnterDela === void 0 ? 0 : _props$mouseEnterDela,
    _props$mouseLeaveDela = props.mouseLeaveDelay,
    mouseLeaveDelay = _props$mouseLeaveDela === void 0 ? 0.1 : _props$mouseLeaveDela,
    overlayStyle = props.overlayStyle,
    _props$prefixCls = props.prefixCls,
    prefixCls = _props$prefixCls === void 0 ? 'rc-tooltip' : _props$prefixCls,
    children = props.children,
    onVisibleChange = props.onVisibleChange,
    afterVisibleChange = props.afterVisibleChange,
    transitionName = props.transitionName,
    animation = props.animation,
    motion = props.motion,
    _props$placement = props.placement,
    placement = _props$placement === void 0 ? 'right' : _props$placement,
    _props$align = props.align,
    align = _props$align === void 0 ? {} : _props$align,
    _props$destroyTooltip = props.destroyTooltipOnHide,
    destroyTooltipOnHide = _props$destroyTooltip === void 0 ? false : _props$destroyTooltip,
    defaultVisible = props.defaultVisible,
    getTooltipContainer = props.getTooltipContainer,
    overlayInnerStyle = props.overlayInnerStyle,
    arrowContent = props.arrowContent,
    overlay = props.overlay,
    id = props.id,
    _props$showArrow = props.showArrow,
    showArrow = _props$showArrow === void 0 ? true : _props$showArrow,
    tooltipClassNames = props.classNames,
    tooltipStyles = props.styles,
    restProps = (0, _objectWithoutProperties2.default)(props, _excluded);
  var mergedId = (0, _useId.default)(id);
  var triggerRef = (0, _react.useRef)(null);
  (0, _react.useImperativeHandle)(ref, function () {
    return triggerRef.current;
  });
  var extraProps = (0, _objectSpread2.default)({}, restProps);
  if ('visible' in props) {
    extraProps.popupVisible = props.visible;
  }
  var getPopupElement = function getPopupElement() {
    return /*#__PURE__*/React.createElement(_Popup.default, {
      key: "content",
      prefixCls: prefixCls,
      id: mergedId,
      bodyClassName: tooltipClassNames === null || tooltipClassNames === void 0 ? void 0 : tooltipClassNames.body,
      overlayInnerStyle: (0, _objectSpread2.default)((0, _objectSpread2.default)({}, overlayInnerStyle), tooltipStyles === null || tooltipStyles === void 0 ? void 0 : tooltipStyles.body)
    }, overlay);
  };
  var getChildren = function getChildren() {
    var child = React.Children.only(children);
    var originalProps = (child === null || child === void 0 ? void 0 : child.props) || {};
    var childProps = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, originalProps), {}, {
      'aria-describedby': overlay ? mergedId : null
    });
    return /*#__PURE__*/React.cloneElement(children, childProps);
  };
  return /*#__PURE__*/React.createElement(_trigger.default, (0, _extends2.default)({
    popupClassName: (0, _classnames.default)(overlayClassName, tooltipClassNames === null || tooltipClassNames === void 0 ? void 0 : tooltipClassNames.root),
    prefixCls: prefixCls,
    popup: getPopupElement,
    action: trigger,
    builtinPlacements: _placements.placements,
    popupPlacement: placement,
    ref: triggerRef,
    popupAlign: align,
    getPopupContainer: getTooltipContainer,
    onPopupVisibleChange: onVisibleChange,
    afterPopupVisibleChange: afterVisibleChange,
    popupTransitionName: transitionName,
    popupAnimation: animation,
    popupMotion: motion,
    defaultPopupVisible: defaultVisible,
    autoDestroy: destroyTooltipOnHide,
    mouseLeaveDelay: mouseLeaveDelay,
    popupStyle: (0, _objectSpread2.default)((0, _objectSpread2.default)({}, overlayStyle), tooltipStyles === null || tooltipStyles === void 0 ? void 0 : tooltipStyles.root),
    mouseEnterDelay: mouseEnterDelay,
    arrow: showArrow
  }, extraProps), getChildren());
};
var _default = exports.default = /*#__PURE__*/(0, _react.forwardRef)(Tooltip);