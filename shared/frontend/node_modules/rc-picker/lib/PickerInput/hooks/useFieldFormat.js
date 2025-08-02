"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.useFieldFormat = useFieldFormat;
var _typeof2 = _interopRequireDefault(require("@babel/runtime/helpers/typeof"));
var React = _interopRequireWildcard(require("react"));
var _miscUtil = require("../../utils/miscUtil");
function useFieldFormat(picker, locale, format) {
  return React.useMemo(function () {
    var rawFormat = (0, _miscUtil.getRowFormat)(picker, locale, format);
    var formatList = (0, _miscUtil.toArray)(rawFormat);
    var firstFormat = formatList[0];
    var maskFormat = (0, _typeof2.default)(firstFormat) === 'object' && firstFormat.type === 'mask' ? firstFormat.format : null;
    return [
    // Format list
    formatList.map(function (config) {
      return typeof config === 'string' || typeof config === 'function' ? config : config.format;
    }),
    // Mask Format
    maskFormat];
  }, [picker, locale, format]);
}