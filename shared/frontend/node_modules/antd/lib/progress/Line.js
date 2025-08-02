"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.sortGradient = exports.handleGradient = exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _colors = require("@ant-design/colors");
var _classnames = _interopRequireDefault(require("classnames"));
var _warning = require("../_util/warning");
var _style = require("./style");
var _utils = require("./utils");
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
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
const sortGradient = gradients => {
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
exports.sortGradient = sortGradient;
const handleGradient = (strokeColor, directionConfig) => {
  const {
      from = _colors.presetPrimaryColors.blue,
      to = _colors.presetPrimaryColors.blue,
      direction = directionConfig === 'rtl' ? 'to left' : 'to right'
    } = strokeColor,
    rest = __rest(strokeColor, ["from", "to", "direction"]);
  if (Object.keys(rest).length !== 0) {
    const sortedGradients = sortGradient(rest);
    const background = `linear-gradient(${direction}, ${sortedGradients})`;
    return {
      background,
      [_style.LineStrokeColorVar]: background
    };
  }
  const background = `linear-gradient(${direction}, ${from}, ${to})`;
  return {
    background,
    [_style.LineStrokeColorVar]: background
  };
};
exports.handleGradient = handleGradient;
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
    [_style.LineStrokeColorVar]: strokeColor,
    background: strokeColor
  };
  const borderRadius = strokeLinecap === 'square' || strokeLinecap === 'butt' ? 0 : undefined;
  const mergedSize = size !== null && size !== void 0 ? size : [-1, strokeWidth || (size === 'small' ? 6 : 8)];
  const [width, height] = (0, _utils.getSize)(mergedSize, 'line', {
    strokeWidth
  });
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('Progress');
    warning.deprecated(!('strokeWidth' in props), 'strokeWidth', 'size');
  }
  const trailStyle = {
    backgroundColor: trailColor || undefined,
    borderRadius
  };
  const percentStyle = Object.assign(Object.assign({
    width: `${(0, _utils.validProgress)(percent)}%`,
    height,
    borderRadius
  }, backgroundProps), {
    [_style.Percent]: (0, _utils.validProgress)(percent) / 100
  });
  const successPercent = (0, _utils.getSuccessPercent)(props);
  const successPercentStyle = {
    width: `${(0, _utils.validProgress)(successPercent)}%`,
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
    className: (0, _classnames.default)(`${prefixCls}-bg`, `${prefixCls}-bg-${infoPosition}`),
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
var _default = exports.default = Line;