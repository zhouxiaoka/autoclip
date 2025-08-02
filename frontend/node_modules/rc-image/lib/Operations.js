"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
var _typeof = require("@babel/runtime/helpers/typeof");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _portal = _interopRequireDefault(require("@rc-component/portal"));
var _classnames4 = _interopRequireDefault(require("classnames"));
var _rcMotion = _interopRequireDefault(require("rc-motion"));
var _KeyCode = _interopRequireDefault(require("rc-util/lib/KeyCode"));
var _react = _interopRequireWildcard(require("react"));
var React = _react;
var _context = require("./context");
function _getRequireWildcardCache(e) { if ("function" != typeof WeakMap) return null; var r = new WeakMap(), t = new WeakMap(); return (_getRequireWildcardCache = function _getRequireWildcardCache(e) { return e ? t : r; })(e); }
function _interopRequireWildcard(e, r) { if (!r && e && e.__esModule) return e; if (null === e || "object" != _typeof(e) && "function" != typeof e) return { default: e }; var t = _getRequireWildcardCache(r); if (t && t.has(e)) return t.get(e); var n = { __proto__: null }, a = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var u in e) if ("default" !== u && Object.prototype.hasOwnProperty.call(e, u)) { var i = a ? Object.getOwnPropertyDescriptor(e, u) : null; i && (i.get || i.set) ? Object.defineProperty(n, u, i) : n[u] = e[u]; } return n.default = e, t && t.set(e, n), n; }
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
  var groupContext = (0, _react.useContext)(_context.PreviewGroupContext);
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
      if (e.keyCode === _KeyCode.default.ESC) {
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
      className: (0, _classnames4.default)(toolClassName, "".concat(prefixCls, "-operations-operation-").concat(type), (0, _defineProperty2.default)({}, "".concat(prefixCls, "-operations-operation-disabled"), !!disabled)),
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
  return /*#__PURE__*/React.createElement(_rcMotion.default, {
    visible: visible,
    motionName: maskTransitionName
  }, function (_ref2) {
    var className = _ref2.className,
      style = _ref2.style;
    return /*#__PURE__*/React.createElement(_portal.default, {
      open: true,
      getContainer: getContainer !== null && getContainer !== void 0 ? getContainer : document.body
    }, /*#__PURE__*/React.createElement("div", {
      className: (0, _classnames4.default)("".concat(prefixCls, "-operations-wrapper"), className, rootClassName),
      style: (0, _objectSpread2.default)((0, _objectSpread2.default)({}, style), {}, {
        zIndex: zIndex
      })
    }, closeIcon === null ? null : /*#__PURE__*/React.createElement("button", {
      className: "".concat(prefixCls, "-close"),
      onClick: onClose
    }, closeIcon || close), showSwitch && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: (0, _classnames4.default)("".concat(prefixCls, "-switch-left"), (0, _defineProperty2.default)({}, "".concat(prefixCls, "-switch-left-disabled"), current === 0)),
      onClick: function onClick(e) {
        return handleActive(e, -1);
      }
    }, left), /*#__PURE__*/React.createElement("div", {
      className: (0, _classnames4.default)("".concat(prefixCls, "-switch-right"), (0, _defineProperty2.default)({}, "".concat(prefixCls, "-switch-right-disabled"), current === count - 1)),
      onClick: function onClick(e) {
        return handleActive(e, 1);
      }
    }, right)), /*#__PURE__*/React.createElement("div", {
      className: "".concat(prefixCls, "-footer")
    }, showProgress && /*#__PURE__*/React.createElement("div", {
      className: "".concat(prefixCls, "-progress")
    }, countRender ? countRender(current + 1, count) : /*#__PURE__*/React.createElement("bdi", null, "".concat(current + 1, " / ").concat(count))), toolbarRender ? toolbarRender(toolbarNode, (0, _objectSpread2.default)((0, _objectSpread2.default)({
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
var _default = exports.default = Operations;