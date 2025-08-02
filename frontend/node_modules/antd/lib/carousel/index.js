"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _reactSlick = _interopRequireDefault(require("@ant-design/react-slick"));
var _classnames = _interopRequireDefault(require("classnames"));
var _context = require("../config-provider/context");
var _style = _interopRequireWildcard(require("./style"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const dotsClass = 'slick-dots';
const ArrowButton = _a => {
  var {
      currentSlide,
      slideCount
    } = _a,
    rest = __rest(_a, ["currentSlide", "slideCount"]);
  return /*#__PURE__*/React.createElement("button", Object.assign({
    type: "button"
  }, rest));
};
const Carousel = /*#__PURE__*/React.forwardRef((props, ref) => {
  const {
      dots = true,
      arrows = false,
      prevArrow = /*#__PURE__*/React.createElement(ArrowButton, {
        "aria-label": "prev"
      }),
      nextArrow = /*#__PURE__*/React.createElement(ArrowButton, {
        "aria-label": "next"
      }),
      draggable = false,
      waitForAnimate = false,
      dotPosition = 'bottom',
      vertical = dotPosition === 'left' || dotPosition === 'right',
      rootClassName,
      className: customClassName,
      style,
      id,
      autoplay = false,
      autoplaySpeed = 3000
    } = props,
    otherProps = __rest(props, ["dots", "arrows", "prevArrow", "nextArrow", "draggable", "waitForAnimate", "dotPosition", "vertical", "rootClassName", "className", "style", "id", "autoplay", "autoplaySpeed"]);
  const {
    getPrefixCls,
    direction,
    className: contextClassName,
    style: contextStyle
  } = (0, _context.useComponentConfig)('carousel');
  const slickRef = React.useRef(null);
  const goTo = (slide, dontAnimate = false) => {
    slickRef.current.slickGoTo(slide, dontAnimate);
  };
  React.useImperativeHandle(ref, () => ({
    goTo,
    autoPlay: slickRef.current.innerSlider.autoPlay,
    innerSlider: slickRef.current.innerSlider,
    prev: slickRef.current.slickPrev,
    next: slickRef.current.slickNext
  }), [slickRef.current]);
  const prevCount = React.useRef(React.Children.count(props.children));
  React.useEffect(() => {
    if (prevCount.current !== React.Children.count(props.children)) {
      goTo(props.initialSlide || 0, false);
      prevCount.current = React.Children.count(props.children);
    }
  }, [props.children]);
  const newProps = Object.assign({
    vertical,
    className: (0, _classnames.default)(customClassName, contextClassName),
    style: Object.assign(Object.assign({}, contextStyle), style),
    autoplay: !!autoplay
  }, otherProps);
  if (newProps.effect === 'fade') {
    newProps.fade = true;
  }
  const prefixCls = getPrefixCls('carousel', newProps.prefixCls);
  const enableDots = !!dots;
  const dsClass = (0, _classnames.default)(dotsClass, `${dotsClass}-${dotPosition}`, typeof dots === 'boolean' ? false : dots === null || dots === void 0 ? void 0 : dots.className);
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls);
  const className = (0, _classnames.default)(prefixCls, {
    [`${prefixCls}-rtl`]: direction === 'rtl',
    [`${prefixCls}-vertical`]: newProps.vertical
  }, hashId, cssVarCls, rootClassName);
  const mergedShowDuration = autoplay && (typeof autoplay === 'object' ? autoplay.dotDuration : false);
  const dotDurationStyle = mergedShowDuration ? {
    [_style.DotDuration]: `${autoplaySpeed}ms`
  } : {};
  return wrapCSSVar(/*#__PURE__*/React.createElement("div", {
    className: className,
    id: id,
    style: dotDurationStyle
  }, /*#__PURE__*/React.createElement(_reactSlick.default, Object.assign({
    ref: slickRef
  }, newProps, {
    dots: enableDots,
    dotsClass: dsClass,
    arrows: arrows,
    prevArrow: prevArrow,
    nextArrow: nextArrow,
    draggable: draggable,
    verticalSwiping: vertical,
    autoplaySpeed: autoplaySpeed,
    waitForAnimate: waitForAnimate
  }))));
});
if (process.env.NODE_ENV !== 'production') {
  Carousel.displayName = 'Carousel';
}
var _default = exports.default = Carousel;