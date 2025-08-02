"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.useQRCode = useQRCode;
var _qrcodegen = require("../libs/qrcodegen");
var _utils = require("../utils");
var _react = require("react");
function useQRCode(_ref) {
  var value = _ref.value,
    level = _ref.level,
    minVersion = _ref.minVersion,
    includeMargin = _ref.includeMargin,
    marginSize = _ref.marginSize,
    imageSettings = _ref.imageSettings,
    size = _ref.size;
  var qrcode = (0, _react.useMemo)(function () {
    var segments = _qrcodegen.QrSegment.makeSegments(value);
    return _qrcodegen.QrCode.encodeSegments(segments, _utils.ERROR_LEVEL_MAP[level], minVersion);
  }, [value, level, minVersion]);
  var _useMemo = (0, _react.useMemo)(function () {
      var cs = qrcode.getModules();
      var mg = (0, _utils.getMarginSize)(includeMargin, marginSize);
      var ncs = cs.length + mg * 2;
      var cis = (0, _utils.getImageSettings)(cs, size, mg, imageSettings);
      return {
        cells: cs,
        margin: mg,
        numCells: ncs,
        calculatedImageSettings: cis
      };
    }, [qrcode, size, imageSettings, includeMargin, marginSize]),
    cells = _useMemo.cells,
    margin = _useMemo.margin,
    numCells = _useMemo.numCells,
    calculatedImageSettings = _useMemo.calculatedImageSettings;
  return {
    qrcode: qrcode,
    margin: margin,
    cells: cells,
    numCells: numCells,
    calculatedImageSettings: calculatedImageSettings
  };
}