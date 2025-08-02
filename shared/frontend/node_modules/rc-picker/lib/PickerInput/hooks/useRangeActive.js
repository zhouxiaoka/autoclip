"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useRangeActive;
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var React = _interopRequireWildcard(require("react"));
var _useLockEffect = _interopRequireDefault(require("./useLockEffect"));
/**
 * When user first focus one input, any submit will trigger focus another one.
 * When second time focus one input, submit will not trigger focus again.
 * When click outside to close the panel, trigger event if it can trigger onChange.
 */
function useRangeActive(disabled) {
  var empty = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : [];
  var mergedOpen = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : false;
  var _React$useState = React.useState(0),
    _React$useState2 = (0, _slicedToArray2.default)(_React$useState, 2),
    activeIndex = _React$useState2[0],
    setActiveIndex = _React$useState2[1];
  var _React$useState3 = React.useState(false),
    _React$useState4 = (0, _slicedToArray2.default)(_React$useState3, 2),
    focused = _React$useState4[0],
    setFocused = _React$useState4[1];
  var activeListRef = React.useRef([]);
  var submitIndexRef = React.useRef(null);
  var lastOperationRef = React.useRef(null);
  var updateSubmitIndex = function updateSubmitIndex(index) {
    submitIndexRef.current = index;
  };
  var hasActiveSubmitValue = function hasActiveSubmitValue(index) {
    return submitIndexRef.current === index;
  };
  var triggerFocus = function triggerFocus(nextFocus) {
    setFocused(nextFocus);
  };

  // ============================= Record =============================
  var lastOperation = function lastOperation(type) {
    if (type) {
      lastOperationRef.current = type;
    }
    return lastOperationRef.current;
  };

  // ============================ Strategy ============================
  // Trigger when input enter or input blur or panel close
  var nextActiveIndex = function nextActiveIndex(nextValue) {
    var list = activeListRef.current;
    var filledActiveSet = new Set(list.filter(function (index) {
      return nextValue[index] || empty[index];
    }));
    var nextIndex = list[list.length - 1] === 0 ? 1 : 0;
    if (filledActiveSet.size >= 2 || disabled[nextIndex]) {
      return null;
    }
    return nextIndex;
  };

  // ============================= Effect =============================
  // Wait in case it's from the click outside to blur
  (0, _useLockEffect.default)(focused || mergedOpen, function () {
    if (!focused) {
      activeListRef.current = [];
      updateSubmitIndex(null);
    }
  });
  React.useEffect(function () {
    if (focused) {
      activeListRef.current.push(activeIndex);
    }
  }, [focused, activeIndex]);
  return [focused, triggerFocus, lastOperation, activeIndex, setActiveIndex, nextActiveIndex, activeListRef.current, updateSubmitIndex, hasActiveSubmitValue];
}