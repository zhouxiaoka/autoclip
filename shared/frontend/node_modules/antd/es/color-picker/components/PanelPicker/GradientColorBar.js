"use client";

import _toConsumableArray from "@babel/runtime/helpers/esm/toConsumableArray";
import * as React from 'react';
import { AggregationColor } from '../../color';
import { getGradientPercentColor } from '../../util';
import { GradientColorSlider } from '../ColorSlider';
function sortColors(colors) {
  return _toConsumableArray(colors).sort((a, b) => a.percent - b.percent);
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
      const newPointColor = getGradientPercentColor(colorList, draggingValue);
      const nextColors = _toConsumableArray(colorList);
      nextColors.splice(draggingIndex, 0, {
        percent: draggingValue,
        color: newPointColor
      });
      colorsRef.current = nextColors;
    } else {
      colorsRef.current = colorList;
    }
    onGradientDragging(true);
    onChange(new AggregationColor(sortColors(colorsRef.current)), true);
  };
  // Adjust color when dragging
  const onDragChange = ({
    deleteIndex,
    draggingIndex,
    draggingValue
  }) => {
    let nextColors = _toConsumableArray(colorsRef.current);
    if (deleteIndex !== -1) {
      nextColors.splice(deleteIndex, 1);
    } else {
      nextColors[draggingIndex] = Object.assign(Object.assign({}, nextColors[draggingIndex]), {
        percent: draggingValue
      });
      nextColors = sortColors(nextColors);
    }
    onChange(new AggregationColor(nextColors), true);
  };
  // ============================== Key ===============================
  const onKeyDelete = index => {
    const nextColors = _toConsumableArray(colorList);
    nextColors.splice(index, 1);
    const nextColor = new AggregationColor(nextColors);
    onChange(nextColor);
    onChangeComplete(nextColor);
  };
  // ============================= Change =============================
  const onInternalChangeComplete = nextValues => {
    onChangeComplete(new AggregationColor(colorList));
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
  return /*#__PURE__*/React.createElement(GradientColorSlider, {
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
export default /*#__PURE__*/React.memo(GradientColorBar);