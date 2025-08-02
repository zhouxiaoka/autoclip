"use client";

import _toConsumableArray from "@babel/runtime/helpers/esm/toConsumableArray";
import React from 'react';
import CloseOutlined from "@ant-design/icons/es/icons/CloseOutlined";
import classNames from 'classnames';
import pickAttrs from "rc-util/es/pickAttrs";
import Button from '../button';
import { useLocale } from '../locale';
import defaultLocale from '../locale/en_US';
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
  const ariaProps = pickAttrs(closable !== null && closable !== void 0 ? closable : {}, true);
  const [contextLocaleGlobal] = useLocale('global', defaultLocale.global);
  const [contextLocaleTour] = useLocale('Tour', defaultLocale.Tour);
  const mergedCloseIcon = /*#__PURE__*/React.createElement("button", Object.assign({
    type: "button",
    onClick: onClose,
    className: `${prefixCls}-close`,
    "aria-label": contextLocaleGlobal === null || contextLocaleGlobal === void 0 ? void 0 : contextLocaleGlobal.close
  }, ariaProps), (closable === null || closable === void 0 ? void 0 : closable.closeIcon) || /*#__PURE__*/React.createElement(CloseOutlined, {
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
  const headerNode = isValidNode(title) ? (/*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-header`
  }, /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-title`
  }, title))) : null;
  const descriptionNode = isValidNode(description) ? (/*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-description`
  }, description)) : null;
  const coverNode = isValidNode(cover) ? /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-cover`
  }, cover) : null;
  let mergedIndicatorNode;
  if (indicatorsRender) {
    mergedIndicatorNode = indicatorsRender(current, total);
  } else {
    mergedIndicatorNode = _toConsumableArray(Array.from({
      length: total
    }).keys()).map((stepItem, index) => (/*#__PURE__*/React.createElement("span", {
      key: stepItem,
      className: classNames(index === current && `${prefixCls}-indicator-active`, `${prefixCls}-indicator`)
    })));
  }
  const mainBtnType = mergedType === 'primary' ? 'default' : 'primary';
  const secondaryBtnProps = {
    type: 'default',
    ghost: mergedType === 'primary'
  };
  const defaultActionsNode = /*#__PURE__*/React.createElement(React.Fragment, null, current !== 0 ? (/*#__PURE__*/React.createElement(Button, Object.assign({
    size: "small"
  }, secondaryBtnProps, prevButtonProps, {
    onClick: prevBtnClick,
    className: classNames(`${prefixCls}-prev-btn`, prevButtonProps === null || prevButtonProps === void 0 ? void 0 : prevButtonProps.className)
  }), (_a = prevButtonProps === null || prevButtonProps === void 0 ? void 0 : prevButtonProps.children) !== null && _a !== void 0 ? _a : contextLocaleTour === null || contextLocaleTour === void 0 ? void 0 : contextLocaleTour.Previous)) : null, /*#__PURE__*/React.createElement(Button, Object.assign({
    size: "small",
    type: mainBtnType
  }, nextButtonProps, {
    onClick: nextBtnClick,
    className: classNames(`${prefixCls}-next-btn`, nextButtonProps === null || nextButtonProps === void 0 ? void 0 : nextButtonProps.className)
  }), (_b = nextButtonProps === null || nextButtonProps === void 0 ? void 0 : nextButtonProps.children) !== null && _b !== void 0 ? _b : isLastStep ? contextLocaleTour === null || contextLocaleTour === void 0 ? void 0 : contextLocaleTour.Finish : contextLocaleTour === null || contextLocaleTour === void 0 ? void 0 : contextLocaleTour.Next));
  return /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-content`
  }, /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-inner`
  }, closable && mergedCloseIcon, coverNode, headerNode, descriptionNode, /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-footer`
  }, total > 1 && /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-indicators`
  }, mergedIndicatorNode), /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-buttons`
  }, actionsRender ? actionsRender(defaultActionsNode, {
    current,
    total
  }) : defaultActionsNode))));
};
export default TourPanel;