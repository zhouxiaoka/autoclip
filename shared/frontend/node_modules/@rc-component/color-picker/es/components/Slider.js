import _slicedToArray from "@babel/runtime/helpers/esm/slicedToArray";
import React, { useRef } from 'react';
import useColorDrag from "../hooks/useColorDrag";
import Palette from "./Palette";
import classNames from 'classnames';
import { useEvent } from 'rc-util';
import { Color } from "../color";
import { calcOffset, calculateColor } from "../util";
import Gradient from "./Gradient";
import Handler from "./Handler";
import Transform from "./Transform";
var Slider = function Slider(props) {
  var prefixCls = props.prefixCls,
    colors = props.colors,
    disabled = props.disabled,
    onChange = props.onChange,
    onChangeComplete = props.onChangeComplete,
    color = props.color,
    type = props.type;
  var sliderRef = useRef();
  var transformRef = useRef();
  var colorRef = useRef(color);
  var getValue = function getValue(c) {
    return type === 'hue' ? c.getHue() : c.a * 100;
  };
  var onDragChange = useEvent(function (offsetValue) {
    var calcColor = calculateColor({
      offset: offsetValue,
      targetRef: transformRef,
      containerRef: sliderRef,
      color: color,
      type: type
    });
    colorRef.current = calcColor;
    onChange(getValue(calcColor));
  });
  var _useColorDrag = useColorDrag({
      color: color,
      targetRef: transformRef,
      containerRef: sliderRef,
      calculate: function calculate() {
        return calcOffset(color, type);
      },
      onDragChange: onDragChange,
      onDragChangeComplete: function onDragChangeComplete() {
        onChangeComplete(getValue(colorRef.current));
      },
      direction: 'x',
      disabledDrag: disabled
    }),
    _useColorDrag2 = _slicedToArray(_useColorDrag, 2),
    offset = _useColorDrag2[0],
    dragStartHandle = _useColorDrag2[1];
  var handleColor = React.useMemo(function () {
    if (type === 'hue') {
      var hsb = color.toHsb();
      hsb.s = 1;
      hsb.b = 1;
      hsb.a = 1;
      var lightColor = new Color(hsb);
      return lightColor;
    }
    return color;
  }, [color, type]);

  // ========================= Gradient =========================
  var gradientList = React.useMemo(function () {
    return colors.map(function (info) {
      return "".concat(info.color, " ").concat(info.percent, "%");
    });
  }, [colors]);

  // ========================== Render ==========================
  return /*#__PURE__*/React.createElement("div", {
    ref: sliderRef,
    className: classNames("".concat(prefixCls, "-slider"), "".concat(prefixCls, "-slider-").concat(type)),
    onMouseDown: dragStartHandle,
    onTouchStart: dragStartHandle
  }, /*#__PURE__*/React.createElement(Palette, {
    prefixCls: prefixCls
  }, /*#__PURE__*/React.createElement(Transform, {
    x: offset.x,
    y: offset.y,
    ref: transformRef
  }, /*#__PURE__*/React.createElement(Handler, {
    size: "small",
    color: handleColor.toHexString(),
    prefixCls: prefixCls
  })), /*#__PURE__*/React.createElement(Gradient, {
    colors: gradientList,
    type: type,
    prefixCls: prefixCls
  })));
};
export default Slider;