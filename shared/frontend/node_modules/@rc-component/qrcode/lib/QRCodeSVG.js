"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.QRCodeSVG = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _objectWithoutProperties2 = _interopRequireDefault(require("@babel/runtime/helpers/objectWithoutProperties"));
var _react = _interopRequireDefault(require("react"));
var _utils = require("./utils");
var _useQRCode2 = require("./hooks/useQRCode");
var _excluded = ["value", "size", "level", "bgColor", "fgColor", "includeMargin", "minVersion", "title", "marginSize", "imageSettings"];
var QRCodeSVG = exports.QRCodeSVG = /*#__PURE__*/_react.default.forwardRef(function QRCodeSVG(props, forwardedRef) {
  var value = props.value,
    _props$size = props.size,
    size = _props$size === void 0 ? _utils.DEFAULT_SIZE : _props$size,
    _props$level = props.level,
    level = _props$level === void 0 ? _utils.DEFAULT_LEVEL : _props$level,
    _props$bgColor = props.bgColor,
    bgColor = _props$bgColor === void 0 ? _utils.DEFAULT_BACKGROUND_COLOR : _props$bgColor,
    _props$fgColor = props.fgColor,
    fgColor = _props$fgColor === void 0 ? _utils.DEFAULT_FRONT_COLOR : _props$fgColor,
    _props$includeMargin = props.includeMargin,
    includeMargin = _props$includeMargin === void 0 ? _utils.DEFAULT_NEED_MARGIN : _props$includeMargin,
    _props$minVersion = props.minVersion,
    minVersion = _props$minVersion === void 0 ? _utils.DEFAULT_MINVERSION : _props$minVersion,
    title = props.title,
    marginSize = props.marginSize,
    imageSettings = props.imageSettings,
    otherProps = (0, _objectWithoutProperties2.default)(props, _excluded);
  var _useQRCode = (0, _useQRCode2.useQRCode)({
      value: value,
      level: level,
      minVersion: minVersion,
      includeMargin: includeMargin,
      marginSize: marginSize,
      imageSettings: imageSettings,
      size: size
    }),
    margin = _useQRCode.margin,
    cells = _useQRCode.cells,
    numCells = _useQRCode.numCells,
    calculatedImageSettings = _useQRCode.calculatedImageSettings;
  var cellsToDraw = cells;
  var image = null;
  if (imageSettings != null && calculatedImageSettings != null) {
    if (calculatedImageSettings.excavation != null) {
      cellsToDraw = (0, _utils.excavateModules)(cells, calculatedImageSettings.excavation);
    }
    image = /*#__PURE__*/_react.default.createElement("image", {
      href: imageSettings.src,
      height: calculatedImageSettings.h,
      width: calculatedImageSettings.w,
      x: calculatedImageSettings.x + margin,
      y: calculatedImageSettings.y + margin,
      preserveAspectRatio: "none",
      opacity: calculatedImageSettings.opacity
      // when crossOrigin is not set, the image will be tainted
      // and the canvas cannot be exported to an image
      ,
      crossOrigin: calculatedImageSettings.crossOrigin
    });
  }
  var fgPath = (0, _utils.generatePath)(cellsToDraw, margin);
  return /*#__PURE__*/_react.default.createElement("svg", (0, _extends2.default)({
    height: size,
    width: size,
    viewBox: "0 0 ".concat(numCells, " ").concat(numCells),
    ref: forwardedRef,
    role: "img"
  }, otherProps), !!title && /*#__PURE__*/_react.default.createElement("title", null, title), /*#__PURE__*/_react.default.createElement("path", {
    fill: bgColor,
    d: "M0,0 h".concat(numCells, "v").concat(numCells, "H0z"),
    shapeRendering: "crispEdges"
  }), /*#__PURE__*/_react.default.createElement("path", {
    fill: fgColor,
    d: fgPath,
    shapeRendering: "crispEdges"
  }), image);
});
QRCodeSVG.displayName = 'QRCodeSVG';