"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useCellRender;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _rcUtil = require("rc-util");
var React = _interopRequireWildcard(require("react"));
function useCellRender(cellRender, dateRender, monthCellRender, range) {
  // ========================= Warn =========================
  if (process.env.NODE_ENV !== 'production') {
    (0, _rcUtil.warning)(!dateRender, "'dateRender' is deprecated. Please use 'cellRender' instead.");
    (0, _rcUtil.warning)(!monthCellRender, "'monthCellRender' is deprecated. Please use 'cellRender' instead.");
  }

  // ======================== Render ========================
  // Merged render
  var mergedCellRender = React.useMemo(function () {
    if (cellRender) {
      return cellRender;
    }
    return function (current, info) {
      var date = current;
      if (dateRender && info.type === 'date') {
        return dateRender(date, info.today);
      }
      if (monthCellRender && info.type === 'month') {
        return monthCellRender(date, info.locale);
      }
      return info.originNode;
    };
  }, [cellRender, monthCellRender, dateRender]);

  // Cell render
  var onInternalCellRender = React.useCallback(function (date, info) {
    return mergedCellRender(date, (0, _objectSpread2.default)((0, _objectSpread2.default)({}, info), {}, {
      range: range
    }));
  }, [mergedCellRender, range]);
  return onInternalCellRender;
}