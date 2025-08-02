"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useSyncState;
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var React = _interopRequireWildcard(require("react"));
var _useEvent = _interopRequireDefault(require("./useEvent"));
/**
 * Same as React.useState but will always get latest state.
 * This is useful when React merge multiple state updates into one.
 * e.g. onTransitionEnd trigger multiple event at once will be merged state update in React.
 */
function useSyncState(defaultValue) {
  var _React$useReducer = React.useReducer(function (x) {
      return x + 1;
    }, 0),
    _React$useReducer2 = (0, _slicedToArray2.default)(_React$useReducer, 2),
    forceUpdate = _React$useReducer2[1];
  var currentValueRef = React.useRef(defaultValue);
  var getValue = (0, _useEvent.default)(function () {
    return currentValueRef.current;
  });
  var setValue = (0, _useEvent.default)(function (updater) {
    currentValueRef.current = typeof updater === 'function' ? updater(currentValueRef.current) : updater;
    forceUpdate();
  });
  return [getValue, setValue];
}