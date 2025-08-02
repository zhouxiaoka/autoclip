"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _trigger = _interopRequireDefault(require("@rc-component/trigger"));
var _classnames = _interopRequireDefault(require("classnames"));
var React = _interopRequireWildcard(require("react"));
var _uiUtil = require("../utils/uiUtil");
var _context = _interopRequireDefault(require("../PickerInput/context"));
var BUILT_IN_PLACEMENTS = {
  bottomLeft: {
    points: ['tl', 'bl'],
    offset: [0, 4],
    overflow: {
      adjustX: 1,
      adjustY: 1
    }
  },
  bottomRight: {
    points: ['tr', 'br'],
    offset: [0, 4],
    overflow: {
      adjustX: 1,
      adjustY: 1
    }
  },
  topLeft: {
    points: ['bl', 'tl'],
    offset: [0, -4],
    overflow: {
      adjustX: 0,
      adjustY: 1
    }
  },
  topRight: {
    points: ['br', 'tr'],
    offset: [0, -4],
    overflow: {
      adjustX: 0,
      adjustY: 1
    }
  }
};
function PickerTrigger(_ref) {
  var popupElement = _ref.popupElement,
    popupStyle = _ref.popupStyle,
    popupClassName = _ref.popupClassName,
    popupAlign = _ref.popupAlign,
    transitionName = _ref.transitionName,
    getPopupContainer = _ref.getPopupContainer,
    children = _ref.children,
    range = _ref.range,
    placement = _ref.placement,
    _ref$builtinPlacement = _ref.builtinPlacements,
    builtinPlacements = _ref$builtinPlacement === void 0 ? BUILT_IN_PLACEMENTS : _ref$builtinPlacement,
    direction = _ref.direction,
    visible = _ref.visible,
    onClose = _ref.onClose;
  var _React$useContext = React.useContext(_context.default),
    prefixCls = _React$useContext.prefixCls;
  var dropdownPrefixCls = "".concat(prefixCls, "-dropdown");
  var realPlacement = (0, _uiUtil.getRealPlacement)(placement, direction === 'rtl');
  return /*#__PURE__*/React.createElement(_trigger.default, {
    showAction: [],
    hideAction: ['click'],
    popupPlacement: realPlacement,
    builtinPlacements: builtinPlacements,
    prefixCls: dropdownPrefixCls,
    popupTransitionName: transitionName,
    popup: popupElement,
    popupAlign: popupAlign,
    popupVisible: visible,
    popupClassName: (0, _classnames.default)(popupClassName, (0, _defineProperty2.default)((0, _defineProperty2.default)({}, "".concat(dropdownPrefixCls, "-range"), range), "".concat(dropdownPrefixCls, "-rtl"), direction === 'rtl')),
    popupStyle: popupStyle,
    stretch: "minWidth",
    getPopupContainer: getPopupContainer,
    onPopupVisibleChange: function onPopupVisibleChange(nextVisible) {
      if (!nextVisible) {
        onClose();
      }
    }
  }, children);
}
var _default = exports.default = PickerTrigger;