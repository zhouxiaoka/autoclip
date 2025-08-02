"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.QRCodeCanvas = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _objectWithoutProperties2 = _interopRequireDefault(require("@babel/runtime/helpers/objectWithoutProperties"));
var _react = _interopRequireWildcard(require("react"));
var _useQRCode2 = require("./hooks/useQRCode");
var _utils = require("./utils");
var _excluded = ["value", "size", "level", "bgColor", "fgColor", "includeMargin", "minVersion", "marginSize", "style", "imageSettings"];
var QRCodeCanvas = exports.QRCodeCanvas = /*#__PURE__*/_react.default.forwardRef(function QRCodeCanvas(props, forwardedRef) {
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
    marginSize = props.marginSize,
    style = props.style,
    imageSettings = props.imageSettings,
    otherProps = (0, _objectWithoutProperties2.default)(props, _excluded);
  var imgSrc = imageSettings === null || imageSettings === void 0 ? void 0 : imageSettings.src;
  var _canvas = (0, _react.useRef)(null);
  var _image = (0, _react.useRef)(null);
  var setCanvasRef = (0, _react.useCallback)(function (node) {
    _canvas.current = node;
    if (typeof forwardedRef === 'function') {
      forwardedRef(node);
    } else if (forwardedRef) {
      forwardedRef.current = node;
    }
  }, [forwardedRef]);
  var _useState = (0, _react.useState)(false),
    _useState2 = (0, _slicedToArray2.default)(_useState, 2),
    setIsImageLoaded = _useState2[1];
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
  (0, _react.useEffect)(function () {
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
          cellsToDraw = (0, _utils.excavateModules)(cells, calculatedImageSettings.excavation);
        }
      }
      var pixelRatio = window.devicePixelRatio || 1;
      canvas.height = canvas.width = size * pixelRatio;
      var scale = size / numCells * pixelRatio;
      ctx.scale(scale, scale);
      ctx.fillStyle = bgColor;
      ctx.fillRect(0, 0, numCells, numCells);
      ctx.fillStyle = fgColor;
      if (_utils.isSupportPath2d) {
        ctx.fill(new Path2D((0, _utils.generatePath)(cellsToDraw, margin)));
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
  (0, _react.useEffect)(function () {
    setIsImageLoaded(false);
  }, [imgSrc]);
  var canvasStyle = (0, _objectSpread2.default)({
    height: size,
    width: size
  }, style);
  var img = null;
  if (imgSrc != null) {
    img = /*#__PURE__*/_react.default.createElement("img", {
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
  return /*#__PURE__*/_react.default.createElement(_react.default.Fragment, null, /*#__PURE__*/_react.default.createElement("canvas", (0, _extends2.default)({
    style: canvasStyle,
    height: size,
    width: size,
    ref: setCanvasRef,
    role: "img"
  }, otherProps)), img);
});
QRCodeCanvas.displayName = 'QRCodeCanvas';