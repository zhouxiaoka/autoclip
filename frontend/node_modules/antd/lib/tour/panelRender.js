"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var _react = _interopRequireDefault(require("react"));
var _CloseOutlined = _interopRequireDefault(require("@ant-design/icons/CloseOutlined"));
var _classnames = _interopRequireDefault(require("classnames"));
var _pickAttrs = _interopRequireDefault(require("rc-util/lib/pickAttrs"));
var _button = _interopRequireDefault(require("../button"));
var _locale = require("../locale");
var _en_US = _interopRequireDefault(require("../locale/en_US"));
function isValidNode(node) {
  return node !== undefined && node !== null;
}
// Due to the independent design of Panel, it will be too coupled to put in rc-tour,
// so a set of Panel logic is implemented separately in antd.
const TourPanel = props => {
  var _a, _b;
  const {
    stepProps,
    current,
    type,
    indicatorsRender,
    actionsRender
  } = props;
  const {
    prefixCls,
    total = 1,
    title,
    onClose,
    onPrev,
    onNext,
    onFinish,
    cover,
    description,
    nextButtonProps,
    prevButtonProps,
    type: stepType,
    closable
  } = stepProps;
  const mergedType = stepType !== null && stepType !== void 0 ? stepType : type;
  const ariaProps = (0, _pickAttrs.default)(closable !== null && closable !== void 0 ? closable : {}, true);
  const [contextLocaleGlobal] = (0, _locale.useLocale)('global', _en_US.default.global);
  const [contextLocaleTour] = (0, _locale.useLocale)('Tour', _en_US.default.Tour);
  const mergedCloseIcon = /*#__PURE__*/_react.default.createElement("button", Object.assign({
    type: "button",
    onClick: onClose,
    className: `${prefixCls}-close`,
    "aria-label": contextLocaleGlobal === null || contextLocaleGlobal === void 0 ? void 0 : contextLocaleGlobal.close
  }, ariaProps), (closable === null || closable === void 0 ? void 0 : closable.closeIcon) || /*#__PURE__*/_react.default.createElement(_CloseOutlined.default, {
    className: `${prefixCls}-close-icon`
  }));
  const isLastStep = current === total - 1;
  const prevBtnClick = () => {
    var _a;
    onPrev === null || onPrev === void 0 ? void 0 : onPrev();
    (_a = prevButtonProps === null || prevButtonProps === void 0 ? void 0 : prevButtonProps.onClick) === null || _a === void 0 ? void 0 : _a.call(prevButtonProps);
  };
  const nextBtnClick = () => {
    var _a;
    if (isLastStep) {
      onFinish === null || onFinish === void 0 ? void 0 : onFinish();
    } else {
      onNext === null || onNext === void 0 ? void 0 : onNext();
    }
    (_a = nextButtonProps === null || nextButtonProps === void 0 ? void 0 : nextButtonProps.onClick) === null || _a === void 0 ? void 0 : _a.call(nextButtonProps);
  };
  const headerNode = isValidNode(title) ? (/*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-header`
  }, /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-title`
  }, title))) : null;
  const descriptionNode = isValidNode(description) ? (/*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-description`
  }, description)) : null;
  const coverNode = isValidNode(cover) ? /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-cover`
  }, cover) : null;
  let mergedIndicatorNode;
  if (indicatorsRender) {
    mergedIndicatorNode = indicatorsRender(current, total);
  } else {
    mergedIndicatorNode = (0, _toConsumableArray2.default)(Array.from({
      length: total
    }).keys()).map((stepItem, index) => (/*#__PURE__*/_react.default.createElement("span", {
      key: stepItem,
      className: (0, _classnames.default)(index === current && `${prefixCls}-indicator-active`, `${prefixCls}-indicator`)
    })));
  }
  const mainBtnType = mergedType === 'primary' ? 'default' : 'primary';
  const secondaryBtnProps = {
    type: 'default',
    ghost: mergedType === 'primary'
  };
  const defaultActionsNode = /*#__PURE__*/_react.default.createElement(_react.default.Fragment, null, current !== 0 ? (/*#__PURE__*/_react.default.createElement(_button.default, Object.assign({
    size: "small"
  }, secondaryBtnProps, prevButtonProps, {
    onClick: prevBtnClick,
    className: (0, _classnames.default)(`${prefixCls}-prev-btn`, prevButtonProps === null || prevButtonProps === void 0 ? void 0 : prevButtonProps.className)
  }), (_a = prevButtonProps === null || prevButtonProps === void 0 ? void 0 : prevButtonProps.children) !== null && _a !== void 0 ? _a : contextLocaleTour === null || contextLocaleTour === void 0 ? void 0 : contextLocaleTour.Previous)) : null, /*#__PURE__*/_react.default.createElement(_button.default, Object.assign({
    size: "small",
    type: mainBtnType
  }, nextButtonProps, {
    onClick: nextBtnClick,
    className: (0, _classnames.default)(`${prefixCls}-next-btn`, nextButtonProps === null || nextButtonProps === void 0 ? void 0 : nextButtonProps.className)
  }), (_b = nextButtonProps === null || nextButtonProps === void 0 ? void 0 : nextButtonProps.children) !== null && _b !== void 0 ? _b : isLastStep ? contextLocaleTour === null || contextLocaleTour === void 0 ? void 0 : contextLocaleTour.Finish : contextLocaleTour === null || contextLocaleTour === void 0 ? void 0 : contextLocaleTour.Next));
  return /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-content`
  }, /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-inner`
  }, closable && mergedCloseIcon, coverNode, headerNode, descriptionNode, /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-footer`
  }, total > 1 && /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-indicators`
  }, mergedIndicatorNode), /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-buttons`
  }, actionsRender ? actionsRender(defaultActionsNode, {
    current,
    total
  }) : defaultActionsNode))));
};
var _default = exports.default = TourPanel;