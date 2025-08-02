"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var React = _interopRequireWildcard(require("react"));
var _context = _interopRequireDefault(require("../context"));
/**
 * Control the active open options path.
 */
var useActive = function useActive(multiple, open) {
  var _React$useContext = React.useContext(_context.default),
    values = _React$useContext.values;
  var firstValueCells = values[0];

  // Record current dropdown active options
  // This also control the open status
  var _React$useState = React.useState([]),
    _React$useState2 = (0, _slicedToArray2.default)(_React$useState, 2),
    activeValueCells = _React$useState2[0],
    setActiveValueCells = _React$useState2[1];
  React.useEffect(function () {
    if (!multiple) {
      setActiveValueCells(firstValueCells || []);
    }
  }, /* eslint-disable react-hooks/exhaustive-deps */
  [open, firstValueCells]
  /* eslint-enable react-hooks/exhaustive-deps */);

  return [activeValueCells, setActiveValueCells];
};
var _default = exports.default = useActive;