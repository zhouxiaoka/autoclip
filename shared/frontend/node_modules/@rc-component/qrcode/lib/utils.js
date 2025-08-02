"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.SPEC_MARGIN_SIZE = exports.ERROR_LEVEL_MAP = exports.DEFAULT_SIZE = exports.DEFAULT_NEED_MARGIN = exports.DEFAULT_MINVERSION = exports.DEFAULT_MARGIN_SIZE = exports.DEFAULT_LEVEL = exports.DEFAULT_IMG_SCALE = exports.DEFAULT_FRONT_COLOR = exports.DEFAULT_BACKGROUND_COLOR = void 0;
exports.excavateModules = excavateModules;
exports.generatePath = generatePath;
exports.getImageSettings = getImageSettings;
exports.getMarginSize = getMarginSize;
exports.isSupportPath2d = void 0;
var _qrcodegen = require("./libs/qrcodegen");
// Part logic is from `qrcode.react`. (ISC License)
// https://github.com/zpao/qrcode.react

// ==========================================================

// =================== ERROR_LEVEL ==========================
var ERROR_LEVEL_MAP = exports.ERROR_LEVEL_MAP = {
  L: _qrcodegen.Ecc.LOW,
  M: _qrcodegen.Ecc.MEDIUM,
  Q: _qrcodegen.Ecc.QUARTILE,
  H: _qrcodegen.Ecc.HIGH
};

// =================== DEFAULT_VALUE ==========================
var DEFAULT_SIZE = exports.DEFAULT_SIZE = 128;
var DEFAULT_LEVEL = exports.DEFAULT_LEVEL = 'L';
var DEFAULT_BACKGROUND_COLOR = exports.DEFAULT_BACKGROUND_COLOR = '#FFFFFF';
var DEFAULT_FRONT_COLOR = exports.DEFAULT_FRONT_COLOR = '#000000';
var DEFAULT_NEED_MARGIN = exports.DEFAULT_NEED_MARGIN = false;
var DEFAULT_MINVERSION = exports.DEFAULT_MINVERSION = 1;
var SPEC_MARGIN_SIZE = exports.SPEC_MARGIN_SIZE = 4;
var DEFAULT_MARGIN_SIZE = exports.DEFAULT_MARGIN_SIZE = 0;
var DEFAULT_IMG_SCALE = exports.DEFAULT_IMG_SCALE = 0.1;

// =================== UTILS ==========================
/**
 * Generate a path string from modules
 * @param modules
 * @param margin 
 * @returns 
 */
function generatePath(modules) {
  var margin = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : 0;
  var ops = [];
  modules.forEach(function (row, y) {
    var start = null;
    row.forEach(function (cell, x) {
      if (!cell && start !== null) {
        ops.push("M".concat(start + margin, " ").concat(y + margin, "h").concat(x - start, "v1H").concat(start + margin, "z"));
        start = null;
        return;
      }
      if (x === row.length - 1) {
        if (!cell) {
          return;
        }
        if (start === null) {
          ops.push("M".concat(x + margin, ",").concat(y + margin, " h1v1H").concat(x + margin, "z"));
        } else {
          ops.push("M".concat(start + margin, ",").concat(y + margin, " h").concat(x + 1 - start, "v1H").concat(start + margin, "z"));
        }
        return;
      }
      if (cell && start === null) {
        start = x;
      }
    });
  });
  return ops.join('');
}
/**
 * Excavate modules
 * @param modules 
 * @param excavation 
 * @returns 
 */
function excavateModules(modules, excavation) {
  return modules.slice().map(function (row, y) {
    if (y < excavation.y || y >= excavation.y + excavation.h) {
      return row;
    }
    return row.map(function (cell, x) {
      if (x < excavation.x || x >= excavation.x + excavation.w) {
        return cell;
      }
      return false;
    });
  });
}

/**
 * Get image settings
 * @param cells The modules of the QR code
 * @param size The size of the QR code
 * @param margin 
 * @param imageSettings 
 * @returns 
 */
function getImageSettings(cells, size, margin, imageSettings) {
  if (imageSettings == null) {
    return null;
  }
  var numCells = cells.length + margin * 2;
  var defaultSize = Math.floor(size * DEFAULT_IMG_SCALE);
  var scale = numCells / size;
  var w = (imageSettings.width || defaultSize) * scale;
  var h = (imageSettings.height || defaultSize) * scale;
  var x = imageSettings.x == null ? cells.length / 2 - w / 2 : imageSettings.x * scale;
  var y = imageSettings.y == null ? cells.length / 2 - h / 2 : imageSettings.y * scale;
  var opacity = imageSettings.opacity == null ? 1 : imageSettings.opacity;
  var excavation = null;
  if (imageSettings.excavate) {
    var floorX = Math.floor(x);
    var floorY = Math.floor(y);
    var ceilW = Math.ceil(w + x - floorX);
    var ceilH = Math.ceil(h + y - floorY);
    excavation = {
      x: floorX,
      y: floorY,
      w: ceilW,
      h: ceilH
    };
  }
  var crossOrigin = imageSettings.crossOrigin;
  return {
    x: x,
    y: y,
    h: h,
    w: w,
    excavation: excavation,
    opacity: opacity,
    crossOrigin: crossOrigin
  };
}

/**
 * Get margin size
 * @param needMargin Whether need margin
 * @param marginSize Custom margin size
 * @returns 
 */
function getMarginSize(needMargin, marginSize) {
  if (marginSize != null) {
    return Math.floor(marginSize);
  }
  return needMargin ? SPEC_MARGIN_SIZE : DEFAULT_MARGIN_SIZE;
}
/**
 * Check if Path2D is supported
 */
var isSupportPath2d = exports.isSupportPath2d = function () {
  try {
    new Path2D().addPath(new Path2D());
  } catch (e) {
    return false;
  }
  return true;
}();