import _extends from "@babel/runtime/helpers/esm/extends";
import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import _slicedToArray from "@babel/runtime/helpers/esm/slicedToArray";
import _objectWithoutProperties from "@babel/runtime/helpers/esm/objectWithoutProperties";
var _excluded = ["value", "size", "level", "bgColor", "fgColor", "includeMargin", "minVersion", "marginSize", "style", "imageSettings"];
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useQRCode } from "./hooks/useQRCode";
import { DEFAULT_BACKGROUND_COLOR, DEFAULT_FRONT_COLOR, DEFAULT_NEED_MARGIN, DEFAULT_LEVEL, DEFAULT_MINVERSION, DEFAULT_SIZE, isSupportPath2d, excavateModules, generatePath } from "./utils";
var QRCodeCanvas = /*#__PURE__*/React.forwardRef(function QRCodeCanvas(props, forwardedRef) {
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
    marginSize = props.marginSize,
    style = props.style,
    imageSettings = props.imageSettings,
    otherProps = _objectWithoutProperties(props, _excluded);
  var imgSrc = imageSettings === null || imageSettings === void 0 ? void 0 : imageSettings.src;
  var _canvas = useRef(null);
  var _image = useRef(null);
  var setCanvasRef = useCallback(function (node) {
    _canvas.current = node;
    if (typeof forwardedRef === 'function') {
      forwardedRef(node);
    } else if (forwardedRef) {
      forwardedRef.current = node;
    }
  }, [forwardedRef]);
  var _useState = useState(false),
    _useState2 = _slicedToArray(_useState, 2),
    setIsImageLoaded = _useState2[1];
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
  useEffect(function () {
    if (_canvas.current != null) {
      var canvas = _canvas.current;
      var ctx = canvas.getContext('2d');
      if (!ctx) {
        return;
      }
      var cellsToDraw = cells;
      var image = _image.current;
      var haveImageToRender = calculatedImageSettings != null && image !== null && image.complete && image.naturalHeight !== 0 && image.naturalWidth !== 0;
      if (haveImageToRender) {
        if (calculatedImageSettings.excavation != null) {
          cellsToDraw = excavateModules(cells, calculatedImageSettings.excavation);
        }
      }
      var pixelRatio = window.devicePixelRatio || 1;
      canvas.height = canvas.width = size * pixelRatio;
      var scale = size / numCells * pixelRatio;
      ctx.scale(scale, scale);
      ctx.fillStyle = bgColor;
      ctx.fillRect(0, 0, numCells, numCells);
      ctx.fillStyle = fgColor;
      if (isSupportPath2d) {
        ctx.fill(new Path2D(generatePath(cellsToDraw, margin)));
      } else {
        cells.forEach(function (row, rdx) {
          row.forEach(function (cell, cdx) {
            if (cell) {
              ctx.fillRect(cdx + margin, rdx + margin, 1, 1);
            }
          });
        });
      }
      if (calculatedImageSettings) {
        ctx.globalAlpha = calculatedImageSettings.opacity;
      }
      if (haveImageToRender) {
        ctx.drawImage(image, calculatedImageSettings.x + margin, calculatedImageSettings.y + margin, calculatedImageSettings.w, calculatedImageSettings.h);
      }
    }
  });
  useEffect(function () {
    setIsImageLoaded(false);
  }, [imgSrc]);
  var canvasStyle = _objectSpread({
    height: size,
    width: size
  }, style);
  var img = null;
  if (imgSrc != null) {
    img = /*#__PURE__*/React.createElement("img", {
      src: imgSrc,
      key: imgSrc,
      style: {
        display: 'none'
      },
      onLoad: function onLoad() {
        setIsImageLoaded(true);
      },
      ref: _image
      // when crossOrigin is not set, the image will be tainted
      // and the canvas cannot be exported to an image
      ,
      crossOrigin: calculatedImageSettings === null || calculatedImageSettings === void 0 ? void 0 : calculatedImageSettings.crossOrigin
    });
  }
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("canvas", _extends({
    style: canvasStyle,
    height: size,
    width: size,
    ref: setCanvasRef,
    role: "img"
  }, otherProps)), img);
});
QRCodeCanvas.displayName = 'QRCodeCanvas';
export { QRCodeCanvas };