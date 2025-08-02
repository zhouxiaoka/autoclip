import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import _defineProperty from "@babel/runtime/helpers/esm/defineProperty";
import Portal from '@rc-component/portal';
import classnames from 'classnames';
import CSSMotion from 'rc-motion';
import KeyCode from "rc-util/es/KeyCode";
import * as React from 'react';
import { useContext } from 'react';
import { PreviewGroupContext } from "./context";
var Operations = function Operations(props) {
  var visible = props.visible,
    maskTransitionName = props.maskTransitionName,
    getContainer = props.getContainer,
    prefixCls = props.prefixCls,
    rootClassName = props.rootClassName,
    icons = props.icons,
    countRender = props.countRender,
    showSwitch = props.showSwitch,
    showProgress = props.showProgress,
    current = props.current,
    transform = props.transform,
    count = props.count,
    scale = props.scale,
    minScale = props.minScale,
    maxScale = props.maxScale,
    closeIcon = props.closeIcon,
    onActive = props.onActive,
    onClose = props.onClose,
    onZoomIn = props.onZoomIn,
    onZoomOut = props.onZoomOut,
    onRotateRight = props.onRotateRight,
    onRotateLeft = props.onRotateLeft,
    onFlipX = props.onFlipX,
    onFlipY = props.onFlipY,
    onReset = props.onReset,
    toolbarRender = props.toolbarRender,
    zIndex = props.zIndex,
    image = props.image;
  var groupContext = useContext(PreviewGroupContext);
  var rotateLeft = icons.rotateLeft,
    rotateRight = icons.rotateRight,
    zoomIn = icons.zoomIn,
    zoomOut = icons.zoomOut,
    close = icons.close,
    left = icons.left,
    right = icons.right,
    flipX = icons.flipX,
    flipY = icons.flipY;
  var toolClassName = "".concat(prefixCls, "-operations-operation");
  React.useEffect(function () {
    var onKeyDown = function onKeyDown(e) {
      if (e.keyCode === KeyCode.ESC) {
        onClose();
      }
    };
    if (visible) {
      window.addEventListener('keydown', onKeyDown);
    }
    return function () {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [visible]);
  var handleActive = function handleActive(e, offset) {
    e.preventDefault();
    e.stopPropagation();
    onActive(offset);
  };
  var renderOperation = React.useCallback(function (_ref) {
    var type = _ref.type,
      disabled = _ref.disabled,
      onClick = _ref.onClick,
      icon = _ref.icon;
    return /*#__PURE__*/React.createElement("div", {
      key: type,
      className: classnames(toolClassName, "".concat(prefixCls, "-operations-operation-").concat(type), _defineProperty({}, "".concat(prefixCls, "-operations-operation-disabled"), !!disabled)),
      onClick: onClick
    }, icon);
  }, [toolClassName, prefixCls]);
  var switchPrevNode = showSwitch ? renderOperation({
    icon: left,
    onClick: function onClick(e) {
      return handleActive(e, -1);
    },
    type: 'prev',
    disabled: current === 0
  }) : undefined;
  var switchNextNode = showSwitch ? renderOperation({
    icon: right,
    onClick: function onClick(e) {
      return handleActive(e, 1);
    },
    type: 'next',
    disabled: current === count - 1
  }) : undefined;
  var flipYNode = renderOperation({
    icon: flipY,
    onClick: onFlipY,
    type: 'flipY'
  });
  var flipXNode = renderOperation({
    icon: flipX,
    onClick: onFlipX,
    type: 'flipX'
  });
  var rotateLeftNode = renderOperation({
    icon: rotateLeft,
    onClick: onRotateLeft,
    type: 'rotateLeft'
  });
  var rotateRightNode = renderOperation({
    icon: rotateRight,
    onClick: onRotateRight,
    type: 'rotateRight'
  });
  var zoomOutNode = renderOperation({
    icon: zoomOut,
    onClick: onZoomOut,
    type: 'zoomOut',
    disabled: scale <= minScale
  });
  var zoomInNode = renderOperation({
    icon: zoomIn,
    onClick: onZoomIn,
    type: 'zoomIn',
    disabled: scale === maxScale
  });
  var toolbarNode = /*#__PURE__*/React.createElement("div", {
    className: "".concat(prefixCls, "-operations")
  }, flipYNode, flipXNode, rotateLeftNode, rotateRightNode, zoomOutNode, zoomInNode);
  return /*#__PURE__*/React.createElement(CSSMotion, {
    visible: visible,
    motionName: maskTransitionName
  }, function (_ref2) {
    var className = _ref2.className,
      style = _ref2.style;
    return /*#__PURE__*/React.createElement(Portal, {
      open: true,
      getContainer: getContainer !== null && getContainer !== void 0 ? getContainer : document.body
    }, /*#__PURE__*/React.createElement("div", {
      className: classnames("".concat(prefixCls, "-operations-wrapper"), className, rootClassName),
      style: _objectSpread(_objectSpread({}, style), {}, {
        zIndex: zIndex
      })
    }, closeIcon === null ? null : /*#__PURE__*/React.createElement("button", {
      className: "".concat(prefixCls, "-close"),
      onClick: onClose
    }, closeIcon || close), showSwitch && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: classnames("".concat(prefixCls, "-switch-left"), _defineProperty({}, "".concat(prefixCls, "-switch-left-disabled"), current === 0)),
      onClick: function onClick(e) {
        return handleActive(e, -1);
      }
    }, left), /*#__PURE__*/React.createElement("div", {
      className: classnames("".concat(prefixCls, "-switch-right"), _defineProperty({}, "".concat(prefixCls, "-switch-right-disabled"), current === count - 1)),
      onClick: function onClick(e) {
        return handleActive(e, 1);
      }
    }, right)), /*#__PURE__*/React.createElement("div", {
      className: "".concat(prefixCls, "-footer")
    }, showProgress && /*#__PURE__*/React.createElement("div", {
      className: "".concat(prefixCls, "-progress")
    }, countRender ? countRender(current + 1, count) : /*#__PURE__*/React.createElement("bdi", null, "".concat(current + 1, " / ").concat(count))), toolbarRender ? toolbarRender(toolbarNode, _objectSpread(_objectSpread({
      icons: {
        prevIcon: switchPrevNode,
        nextIcon: switchNextNode,
        flipYIcon: flipYNode,
        flipXIcon: flipXNode,
        rotateLeftIcon: rotateLeftNode,
        rotateRightIcon: rotateRightNode,
        zoomOutIcon: zoomOutNode,
        zoomInIcon: zoomInNode
      },
      actions: {
        onActive: onActive,
        onFlipY: onFlipY,
        onFlipX: onFlipX,
        onRotateLeft: onRotateLeft,
        onRotateRight: onRotateRight,
        onZoomOut: onZoomOut,
        onZoomIn: onZoomIn,
        onReset: onReset,
        onClose: onClose
      },
      transform: transform
    }, groupContext ? {
      current: current,
      total: count
    } : {}), {}, {
      image: image
    })) : toolbarNode)));
  });
};
export default Operations;