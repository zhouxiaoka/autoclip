"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = exports.GradientColorSlider = void 0;
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcSlider = require("rc-slider");
var _useEvent = _interopRequireDefault(require("rc-util/lib/hooks/useEvent"));
var _slider = _interopRequireDefault(require("../../slider"));
var _Context = _interopRequireDefault(require("../../slider/Context"));
var _util = require("../util");
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const GradientColorSlider = props => {
  const {
      prefixCls,
      colors,
      type,
      color,
      range = false,
      className,
      activeIndex,
      onActive,
      onDragStart,
      onDragChange,
      onKeyDelete
    } = props,
    restProps = __rest(props, ["prefixCls", "colors", "type", "color", "range", "className", "activeIndex", "onActive", "onDragStart", "onDragChange", "onKeyDelete"]);
  const sliderProps = Object.assign(Object.assign({}, restProps), {
    track: false
  });
  // ========================== Background ==========================
  const linearCss = React.useMemo(() => {
    const colorsStr = colors.map(c => `${c.color} ${c.percent}%`).join(', ');
    return `linear-gradient(90deg, ${colorsStr})`;
  }, [colors]);
  const pointColor = React.useMemo(() => {
    if (!color || !type) {
      return null;
    }
    if (type === 'alpha') {
      return color.toRgbString();
    }
    return `hsl(${color.toHsb().h}, 100%, 50%)`;
  }, [color, type]);
  // ======================= Context: Slider ========================
  const onInternalDragStart = (0, _useEvent.default)(onDragStart);
  const onInternalDragChange = (0, _useEvent.default)(onDragChange);
  const unstableContext = React.useMemo(() => ({
    onDragStart: onInternalDragStart,
    onDragChange: onInternalDragChange
  }), []);
  // ======================= Context: Render ========================
  const handleRender = (0, _useEvent.default)((ori, info) => {
    const {
      onFocus,
      style,
      className: handleCls,
      onKeyDown
    } = ori.props;
    // Point Color
    const mergedStyle = Object.assign({}, style);
    if (type === 'gradient') {
      mergedStyle.background = (0, _util.getGradientPercentColor)(colors, info.value);
    }
    return /*#__PURE__*/React.cloneElement(ori, {
      onFocus: e => {
        onActive === null || onActive === void 0 ? void 0 : onActive(info.index);
        onFocus === null || onFocus === void 0 ? void 0 : onFocus(e);
      },
      style: mergedStyle,
      className: (0, _classnames.default)(handleCls, {
        [`${prefixCls}-slider-handle-active`]: activeIndex === info.index
      }),
      onKeyDown: e => {
        if ((e.key === 'Delete' || e.key === 'Backspace') && onKeyDelete) {
          onKeyDelete(info.index);
        }
        onKeyDown === null || onKeyDown === void 0 ? void 0 : onKeyDown(e);
      }
    });
  });
  const sliderContext = React.useMemo(() => ({
    direction: 'ltr',
    handleRender
  }), []);
  // ============================ Render ============================
  return /*#__PURE__*/React.createElement(_Context.default.Provider, {
    value: sliderContext
  }, /*#__PURE__*/React.createElement(_rcSlider.UnstableContext.Provider, {
    value: unstableContext
  }, /*#__PURE__*/React.createElement(_slider.default, Object.assign({}, sliderProps, {
    className: (0, _classnames.default)(className, `${prefixCls}-slider`),
    tooltip: {
      open: false
    },
    range: {
      editable: range,
      minCount: 2
    },
    styles: {
      rail: {
        background: linearCss
      },
      handle: pointColor ? {
        background: pointColor
      } : {}
    },
    classNames: {
      rail: `${prefixCls}-slider-rail`,
      handle: `${prefixCls}-slider-handle`
    }
  }))));
};
exports.GradientColorSlider = GradientColorSlider;
const SingleColorSlider = props => {
  const {
    value,
    onChange,
    onChangeComplete
  } = props;
  const singleOnChange = v => onChange(v[0]);
  const singleOnChangeComplete = v => onChangeComplete(v[0]);
  return /*#__PURE__*/React.createElement(GradientColorSlider, Object.assign({}, props, {
    value: [value],
    onChange: singleOnChange,
    onChangeComplete: singleOnChangeComplete
  }));
};
var _default = exports.default = SingleColorSlider;