"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _react = _interopRequireWildcard(require("react"));
var _useColorDrag3 = _interopRequireDefault(require("../hooks/useColorDrag"));
var _Palette = _interopRequireDefault(require("./Palette"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcUtil = require("rc-util");
var _color = require("../color");
var _util = require("../util");
var _Gradient = _interopRequireDefault(require("./Gradient"));
var _Handler = _interopRequireDefault(require("./Handler"));
var _Transform = _interopRequireDefault(require("./Transform"));
var Slider = function Slider(props) {
  var prefixCls = props.prefixCls,
    colors = props.colors,
    disabled = props.disabled,
    onChange = props.onChange,
    onChangeComplete = props.onChangeComplete,
    color = props.color,
    type = props.type;
  var sliderRef = (0, _react.useRef)();
  var transformRef = (0, _react.useRef)();
  var colorRef = (0, _react.useRef)(color);
  var getValue = function getValue(c) {
    return type === 'hue' ? c.getHue() : c.a * 100;
  };
  var onDragChange = (0, _rcUtil.useEvent)(function (offsetValue) {
    var calcColor = (0, _util.calculateColor)({
      offset: offsetValue,
      targetRef: transformRef,
      containerRef: sliderRef,
      color: color,
      type: type
    });
    colorRef.current = calcColor;
    onChange(getValue(calcColor));
  });
  var _useColorDrag = (0, _useColorDrag3.default)({
      color: color,
      targetRef: transformRef,
      containerRef: sliderRef,
      calculate: function calculate() {
        return (0, _util.calcOffset)(color, type);
      },
      onDragChange: onDragChange,
      onDragChangeComplete: function onDragChangeComplete() {
        onChangeComplete(getValue(colorRef.current));
      },
      direction: 'x',
      disabledDrag: disabled
    }),
    _useColorDrag2 = (0, _slicedToArray2.default)(_useColorDrag, 2),
    offset = _useColorDrag2[0],
    dragStartHandle = _useColorDrag2[1];
  var handleColor = _react.default.useMemo(function () {
    if (type === 'hue') {
      var hsb = color.toHsb();
      hsb.s = 1;
      hsb.b = 1;
      hsb.a = 1;
      var lightColor = new _color.Color(hsb);
      return lightColor;
    }
    return color;
  }, [color, type]);

  // ========================= Gradient =========================
  var gradientList = _react.default.useMemo(function () {
    return colors.map(function (info) {
      return "".concat(info.color, " ").concat(info.percent, "%");
    });
  }, [colors]);

  // ========================== Render ==========================
  return /*#__PURE__*/_react.default.createElement("div", {
    ref: sliderRef,
    className: (0, _classnames.default)("".concat(prefixCls, "-slider"), "".concat(prefixCls, "-slider-").concat(type)),
    onMouseDown: dragStartHandle,
    onTouchStart: dragStartHandle
  }, /*#__PURE__*/_react.default.createElement(_Palette.default, {
    prefixCls: prefixCls
  }, /*#__PURE__*/_react.default.createElement(_Transform.default, {
    x: offset.x,
    y: offset.y,
    ref: transformRef
  }, /*#__PURE__*/_react.default.createElement(_Handler.default, {
    size: "small",
    color: handleColor.toHexString(),
    prefixCls: prefixCls
  })), /*#__PURE__*/_react.default.createElement(_Gradient.default, {
    colors: gradientList,
    type: type,
    prefixCls: prefixCls
  })));
};
var _default = exports.default = Slider;