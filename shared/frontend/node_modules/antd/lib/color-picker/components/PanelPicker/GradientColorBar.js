"use strict";
"use client";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var React = _interopRequireWildcard(require("react"));
var _color = require("../../color");
var _util = require("../../util");
var _ColorSlider = require("../ColorSlider");
function sortColors(colors) {
  return (0, _toConsumableArray2.default)(colors).sort((a, b) => a.percent - b.percent);
}
/**
 * GradientColorBar will auto show when the mode is `gradient`.
 */
const GradientColorBar = props => {
  const {
    prefixCls,
    mode,
    onChange,
    onChangeComplete,
    onActive,
    activeIndex,
    onGradientDragging,
    colors
  } = props;
  const isGradient = mode === 'gradient';
  // ============================= Colors =============================
  const colorList = React.useMemo(() => colors.map(info => ({
    percent: info.percent,
    color: info.color.toRgbString()
  })), [colors]);
  const values = React.useMemo(() => colorList.map(info => info.percent), [colorList]);
  // ============================== Drag ==============================
  const colorsRef = React.useRef(colorList);
  // Record current colors
  const onDragStart = ({
    rawValues,
    draggingIndex,
    draggingValue
  }) => {
    if (rawValues.length > colorList.length) {
      // Add new node
      const newPointColor = (0, _util.getGradientPercentColor)(colorList, draggingValue);
      const nextColors = (0, _toConsumableArray2.default)(colorList);
      nextColors.splice(draggingIndex, 0, {
        percent: draggingValue,
        color: newPointColor
      });
      colorsRef.current = nextColors;
    } else {
      colorsRef.current = colorList;
    }
    onGradientDragging(true);
    onChange(new _color.AggregationColor(sortColors(colorsRef.current)), true);
  };
  // Adjust color when dragging
  const onDragChange = ({
    deleteIndex,
    draggingIndex,
    draggingValue
  }) => {
    let nextColors = (0, _toConsumableArray2.default)(colorsRef.current);
    if (deleteIndex !== -1) {
      nextColors.splice(deleteIndex, 1);
    } else {
      nextColors[draggingIndex] = Object.assign(Object.assign({}, nextColors[draggingIndex]), {
        percent: draggingValue
      });
      nextColors = sortColors(nextColors);
    }
    onChange(new _color.AggregationColor(nextColors), true);
  };
  // ============================== Key ===============================
  const onKeyDelete = index => {
    const nextColors = (0, _toConsumableArray2.default)(colorList);
    nextColors.splice(index, 1);
    const nextColor = new _color.AggregationColor(nextColors);
    onChange(nextColor);
    onChangeComplete(nextColor);
  };
  // ============================= Change =============================
  const onInternalChangeComplete = nextValues => {
    onChangeComplete(new _color.AggregationColor(colorList));
    // Reset `activeIndex` if out of range
    if (activeIndex >= nextValues.length) {
      onActive(nextValues.length - 1);
    }
    onGradientDragging(false);
  };
  // ============================= Render =============================
  if (!isGradient) {
    return null;
  }
  return /*#__PURE__*/React.createElement(_ColorSlider.GradientColorSlider, {
    min: 0,
    max: 100,
    prefixCls: prefixCls,
    className: `${prefixCls}-gradient-slider`,
    colors: colorList,
    color: null,
    value: values,
    range: true,
    onChangeComplete: onInternalChangeComplete,
    disabled: false,
    type: "gradient",
    // Active
    activeIndex: activeIndex,
    onActive: onActive,
    // Drag
    onDragStart: onDragStart,
    onDragChange: onDragChange,
    onKeyDelete: onKeyDelete
  });
};
var _default = exports.default = /*#__PURE__*/React.memo(GradientColorBar);