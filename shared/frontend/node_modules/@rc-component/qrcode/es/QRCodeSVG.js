import _extends from "@babel/runtime/helpers/esm/extends";
import _objectWithoutProperties from "@babel/runtime/helpers/esm/objectWithoutProperties";
var _excluded = ["value", "size", "level", "bgColor", "fgColor", "includeMargin", "minVersion", "title", "marginSize", "imageSettings"];
import React from 'react';
import { DEFAULT_BACKGROUND_COLOR, DEFAULT_FRONT_COLOR, DEFAULT_NEED_MARGIN, DEFAULT_LEVEL, DEFAULT_MINVERSION, DEFAULT_SIZE, excavateModules, generatePath } from "./utils";
import { useQRCode } from "./hooks/useQRCode";
var QRCodeSVG = /*#__PURE__*/React.forwardRef(function QRCodeSVG(props, forwardedRef) {
  var value = props.value,
    _props$size = props.size,
    size = _props$size === void 0 ? DEFAULT_SIZE : _props$size,
    _props$level = props.level,
    level = _props$level === void 0 ? DEFAULT_LEVEL : _props$level,
    _props$bgColor = props.bgColor,
    bgColor = _props$bgColor === void 0 ? DEFAULT_BACKGROUND_COLOR : _props$bgColor,
    _props$fgColor = props.fgColor,
    fgColor = _props$fgColor === void 0 ? DEFAULT_FRONT_COLOR : _props$fgColor,
    _props$includeMargin = props.includeMargin,
    includeMargin = _props$includeMargin === void 0 ? DEFAULT_NEED_MARGIN : _props$includeMargin,
    _props$minVersion = props.minVersion,
    minVersion = _props$minVersion === void 0 ? DEFAULT_MINVERSION : _props$minVersion,
    title = props.title,
    marginSize = props.marginSize,
    imageSettings = props.imageSettings,
    otherProps = _objectWithoutProperties(props, _excluded);
  var _useQRCode = useQRCode({
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
      cellsToDraw = excavateModules(cells, calculatedImageSettings.excavation);
    }
    image = /*#__PURE__*/React.createElement("image", {
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
  var fgPath = generatePath(cellsToDraw, margin);
  return /*#__PURE__*/React.createElement("svg", _extends({
    height: size,
    width: size,
    viewBox: "0 0 ".concat(numCells, " ").concat(numCells),
    ref: forwardedRef,
    role: "img"
  }, otherProps), !!title && /*#__PURE__*/React.createElement("title", null, title), /*#__PURE__*/React.createElement("path", {
    fill: bgColor,
    d: "M0,0 h".concat(numCells, "v").concat(numCells, "H0z"),
    shapeRendering: "crispEdges"
  }), /*#__PURE__*/React.createElement("path", {
    fill: fgColor,
    d: fgPath,
    shapeRendering: "crispEdges"
  }), image);
});
QRCodeSVG.displayName = 'QRCodeSVG';
export { QRCodeSVG };