"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import * as React from 'react';
import { presetPrimaryColors } from '@ant-design/colors';
import classNames from 'classnames';
import { devUseWarning } from '../_util/warning';
import { LineStrokeColorVar, Percent } from './style';
import { getSize, getSuccessPercent, validProgress } from './utils';
/**
 * @example
 *   {
 *     "0%": "#afc163",
 *     "75%": "#009900",
 *     "50%": "green", // ====> '#afc163 0%, #66FF00 25%, #00CC00 50%, #009900 75%, #ffffff 100%'
 *     "25%": "#66FF00",
 *     "100%": "#ffffff"
 *   }
 */
export const sortGradient = gradients => {
  let tempArr = [];
  Object.keys(gradients).forEach(key => {
    const formattedKey = parseFloat(key.replace(/%/g, ''));
    if (!Number.isNaN(formattedKey)) {
      tempArr.push({
        key: formattedKey,
        value: gradients[key]
      });
    }
  });
  tempArr = tempArr.sort((a, b) => a.key - b.key);
  return tempArr.map(({
    key,
    value
  }) => `${value} ${key}%`).join(', ');
};
/**
 * Then this man came to realize the truth: Besides six pence, there is the moon. Besides bread and
 * butter, there is the bug. And... Besides women, there is the code.
 *
 * @example
 *   {
 *     "0%": "#afc163",
 *     "25%": "#66FF00",
 *     "50%": "#00CC00", // ====>  linear-gradient(to right, #afc163 0%, #66FF00 25%,
 *     "75%": "#009900", //        #00CC00 50%, #009900 75%, #ffffff 100%)
 *     "100%": "#ffffff"
 *   }
 */
export const handleGradient = (strokeColor, directionConfig) => {
  const {
      from = presetPrimaryColors.blue,
      to = presetPrimaryColors.blue,
      direction = directionConfig === 'rtl' ? 'to left' : 'to right'
    } = strokeColor,
    rest = __rest(strokeColor, ["from", "to", "direction"]);
  if (Object.keys(rest).length !== 0) {
    const sortedGradients = sortGradient(rest);
    const background = `linear-gradient(${direction}, ${sortedGradients})`;
    return {
      background,
      [LineStrokeColorVar]: background
    };
  }
  const background = `linear-gradient(${direction}, ${from}, ${to})`;
  return {
    background,
    [LineStrokeColorVar]: background
  };
};
const Line = props => {
  const {
    prefixCls,
    direction: directionConfig,
    percent,
    size,
    strokeWidth,
    strokeColor,
    strokeLinecap = 'round',
    children,
    trailColor = null,
    percentPosition,
    success
  } = props;
  const {
    align: infoAlign,
    type: infoPosition
  } = percentPosition;
  const backgroundProps = strokeColor && typeof strokeColor !== 'string' ? handleGradient(strokeColor, directionConfig) : {
    [LineStrokeColorVar]: strokeColor,
    background: strokeColor
  };
  const borderRadius = strokeLinecap === 'square' || strokeLinecap === 'butt' ? 0 : undefined;
  const mergedSize = size !== null && size !== void 0 ? size : [-1, strokeWidth || (size === 'small' ? 6 : 8)];
  const [width, height] = getSize(mergedSize, 'line', {
    strokeWidth
  });
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Progress');
    warning.deprecated(!('strokeWidth' in props), 'strokeWidth', 'size');
  }
  const trailStyle = {
    backgroundColor: trailColor || undefined,
    borderRadius
  };
  const percentStyle = Object.assign(Object.assign({
    width: `${validProgress(percent)}%`,
    height,
    borderRadius
  }, backgroundProps), {
    [Percent]: validProgress(percent) / 100
  });
  const successPercent = getSuccessPercent(props);
  const successPercentStyle = {
    width: `${validProgress(successPercent)}%`,
    height,
    borderRadius,
    backgroundColor: success === null || success === void 0 ? void 0 : success.strokeColor
  };
  const outerStyle = {
    width: width < 0 ? '100%' : width
  };
  const lineInner = /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-inner`,
    style: trailStyle
  }, /*#__PURE__*/React.createElement("div", {
    className: classNames(`${prefixCls}-bg`, `${prefixCls}-bg-${infoPosition}`),
    style: percentStyle
  }, infoPosition === 'inner' && children), successPercent !== undefined && (/*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-success-bg`,
    style: successPercentStyle
  })));
  const isOuterStart = infoPosition === 'outer' && infoAlign === 'start';
  const isOuterEnd = infoPosition === 'outer' && infoAlign === 'end';
  return infoPosition === 'outer' && infoAlign === 'center' ? (/*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-layout-bottom`
  }, lineInner, children)) : (/*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-outer`,
    style: outerStyle
  }, isOuterStart && children, lineInner, isOuterEnd && children));
};
export default Line;