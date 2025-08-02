import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { Color } from "./color";
export var ColorPickerPrefixCls = 'rc-color-picker';
export var generateColor = function generateColor(color) {
  if (color instanceof Color) {
    return color;
  }
  return new Color(color);
};
export var defaultColor = generateColor('#1677ff');
export var calculateColor = function calculateColor(props) {
  var offset = props.offset,
    targetRef = props.targetRef,
    containerRef = props.containerRef,
    color = props.color,
    type = props.type;
  var _containerRef$current = containerRef.current.getBoundingClientRect(),
    width = _containerRef$current.width,
    height = _containerRef$current.height;
  var _targetRef$current$ge = targetRef.current.getBoundingClientRect(),
    targetWidth = _targetRef$current$ge.width,
    targetHeight = _targetRef$current$ge.height;
  var centerOffsetX = targetWidth / 2;
  var centerOffsetY = targetHeight / 2;
  var saturation = (offset.x + centerOffsetX) / width;
  var bright = 1 - (offset.y + centerOffsetY) / height;
  var hsb = color.toHsb();
  var alphaOffset = saturation;
  var hueOffset = (offset.x + centerOffsetX) / width * 360;
  if (type) {
    switch (type) {
      case 'hue':
        return generateColor(_objectSpread(_objectSpread({}, hsb), {}, {
          h: hueOffset <= 0 ? 0 : hueOffset
        }));
      case 'alpha':
        return generateColor(_objectSpread(_objectSpread({}, hsb), {}, {
          a: alphaOffset <= 0 ? 0 : alphaOffset
        }));
    }
  }
  return generateColor({
    h: hsb.h,
    s: saturation <= 0 ? 0 : saturation,
    b: bright >= 1 ? 1 : bright,
    a: hsb.a
  });
};
export var calcOffset = function calcOffset(color, type) {
  var hsb = color.toHsb();
  switch (type) {
    case 'hue':
      return {
        x: hsb.h / 360 * 100,
        y: 50
      };
    case 'alpha':
      return {
        x: color.a * 100,
        y: 50
      };

    // Picker panel
    default:
      return {
        x: hsb.s * 100,
        y: (1 - hsb.b) * 100
      };
  }
};