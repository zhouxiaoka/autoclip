import { QrCode, QrSegment } from "../libs/qrcodegen";
import { ERROR_LEVEL_MAP, getImageSettings, getMarginSize } from "../utils";
import { useMemo } from 'react';
export function useQRCode(_ref) {
  var value = _ref.value,
    level = _ref.level,
    minVersion = _ref.minVersion,
    includeMargin = _ref.includeMargin,
    marginSize = _ref.marginSize,
    imageSettings = _ref.imageSettings,
    size = _ref.size;
  var qrcode = useMemo(function () {
    var segments = QrSegment.makeSegments(value);
    return QrCode.encodeSegments(segments, ERROR_LEVEL_MAP[level], minVersion);
  }, [value, level, minVersion]);
  var _useMemo = useMemo(function () {
      var cs = qrcode.getModules();
      var mg = getMarginSize(includeMargin, marginSize);
      var ncs = cs.length + mg * 2;
      var cis = getImageSettings(cs, size, mg, imageSettings);
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