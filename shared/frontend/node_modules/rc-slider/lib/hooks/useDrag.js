"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
var _typeof = require("@babel/runtime/helpers/typeof");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var React = _interopRequireWildcard(require("react"));
var _useEvent = _interopRequireDefault(require("rc-util/lib/hooks/useEvent"));
var _useLayoutEffect = _interopRequireDefault(require("rc-util/lib/hooks/useLayoutEffect"));
var _context = require("../context");
function _getRequireWildcardCache(e) { if ("function" != typeof WeakMap) return null; var r = new WeakMap(), t = new WeakMap(); return (_getRequireWildcardCache = function _getRequireWildcardCache(e) { return e ? t : r; })(e); }
function _interopRequireWildcard(e, r) { if (!r && e && e.__esModule) return e; if (null === e || "object" != _typeof(e) && "function" != typeof e) return { default: e }; var t = _getRequireWildcardCache(r); if (t && t.has(e)) return t.get(e); var n = { __proto__: null }, a = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var u in e) if ("default" !== u && Object.prototype.hasOwnProperty.call(e, u)) { var i = a ? Object.getOwnPropertyDescriptor(e, u) : null; i && (i.get || i.set) ? Object.defineProperty(n, u, i) : n[u] = e[u]; } return n.default = e, t && t.set(e, n), n; }
/** Drag to delete offset. It's a user experience number for dragging out */
var REMOVE_DIST = 130;
function getPosition(e) {
  var obj = 'targetTouches' in e ? e.targetTouches[0] : e;
  return {
    pageX: obj.pageX,
    pageY: obj.pageY
  };
}
function useDrag(containerRef, direction, rawValues, min, max, formatValue, triggerChange, finishChange, offsetValues, editable, minCount) {
  var _React$useState = React.useState(null),
    _React$useState2 = (0, _slicedToArray2.default)(_React$useState, 2),
    draggingValue = _React$useState2[0],
    setDraggingValue = _React$useState2[1];
  var _React$useState3 = React.useState(-1),
    _React$useState4 = (0, _slicedToArray2.default)(_React$useState3, 2),
    draggingIndex = _React$useState4[0],
    setDraggingIndex = _React$useState4[1];
  var _React$useState5 = React.useState(false),
    _React$useState6 = (0, _slicedToArray2.default)(_React$useState5, 2),
    draggingDelete = _React$useState6[0],
    setDraggingDelete = _React$useState6[1];
  var _React$useState7 = React.useState(rawValues),
    _React$useState8 = (0, _slicedToArray2.default)(_React$useState7, 2),
    cacheValues = _React$useState8[0],
    setCacheValues = _React$useState8[1];
  var _React$useState9 = React.useState(rawValues),
    _React$useState10 = (0, _slicedToArray2.default)(_React$useState9, 2),
    originValues = _React$useState10[0],
    setOriginValues = _React$useState10[1];
  var mouseMoveEventRef = React.useRef(null);
  var mouseUpEventRef = React.useRef(null);
  var touchEventTargetRef = React.useRef(null);
  var _React$useContext = React.useContext(_context.UnstableContext),
    onDragStart = _React$useContext.onDragStart,
    onDragChange = _React$useContext.onDragChange;
  (0, _useLayoutEffect.default)(function () {
    if (draggingIndex === -1) {
      setCacheValues(rawValues);
    }
  }, [rawValues, draggingIndex]);

  // Clean up event
  React.useEffect(function () {
    return function () {
      document.removeEventListener('mousemove', mouseMoveEventRef.current);
      document.removeEventListener('mouseup', mouseUpEventRef.current);
      if (touchEventTargetRef.current) {
        touchEventTargetRef.current.removeEventListener('touchmove', mouseMoveEventRef.current);
        touchEventTargetRef.current.removeEventListener('touchend', mouseUpEventRef.current);
      }
    };
  }, []);
  var flushValues = function flushValues(nextValues, nextValue, deleteMark) {
    // Perf: Only update state when value changed
    if (nextValue !== undefined) {
      setDraggingValue(nextValue);
    }
    setCacheValues(nextValues);
    var changeValues = nextValues;
    if (deleteMark) {
      changeValues = nextValues.filter(function (_, i) {
        return i !== draggingIndex;
      });
    }
    triggerChange(changeValues);
    if (onDragChange) {
      onDragChange({
        rawValues: nextValues,
        deleteIndex: deleteMark ? draggingIndex : -1,
        draggingIndex: draggingIndex,
        draggingValue: nextValue
      });
    }
  };
  var updateCacheValue = (0, _useEvent.default)(function (valueIndex, offsetPercent, deleteMark) {
    if (valueIndex === -1) {
      // >>>> Dragging on the track
      var startValue = originValues[0];
      var endValue = originValues[originValues.length - 1];
      var maxStartOffset = min - startValue;
      var maxEndOffset = max - endValue;

      // Get valid offset
      var offset = offsetPercent * (max - min);
      offset = Math.max(offset, maxStartOffset);
      offset = Math.min(offset, maxEndOffset);

      // Use first value to revert back of valid offset (like steps marks)
      var formatStartValue = formatValue(startValue + offset);
      offset = formatStartValue - startValue;
      var cloneCacheValues = originValues.map(function (val) {
        return val + offset;
      });
      flushValues(cloneCacheValues);
    } else {
      // >>>> Dragging on the handle
      var offsetDist = (max - min) * offsetPercent;

      // Always start with the valueIndex origin value
      var cloneValues = (0, _toConsumableArray2.default)(cacheValues);
      cloneValues[valueIndex] = originValues[valueIndex];
      var next = offsetValues(cloneValues, offsetDist, valueIndex, 'dist');
      flushValues(next.values, next.value, deleteMark);
    }
  });
  var onStartMove = function onStartMove(e, valueIndex, startValues) {
    e.stopPropagation();

    // 如果是点击 track 触发的，需要传入变化后的初始值，而不能直接用 rawValues
    var initialValues = startValues || rawValues;
    var originValue = initialValues[valueIndex];
    setDraggingIndex(valueIndex);
    setDraggingValue(originValue);
    setOriginValues(initialValues);
    setCacheValues(initialValues);
    setDraggingDelete(false);
    var _getPosition = getPosition(e),
      startX = _getPosition.pageX,
      startY = _getPosition.pageY;

    // We declare it here since closure can't get outer latest value
    var deleteMark = false;

    // Internal trigger event
    if (onDragStart) {
      onDragStart({
        rawValues: initialValues,
        draggingIndex: valueIndex,
        draggingValue: originValue
      });
    }

    // Moving
    var onMouseMove = function onMouseMove(event) {
      event.preventDefault();
      var _getPosition2 = getPosition(event),
        moveX = _getPosition2.pageX,
        moveY = _getPosition2.pageY;
      var offsetX = moveX - startX;
      var offsetY = moveY - startY;
      var _containerRef$current = containerRef.current.getBoundingClientRect(),
        width = _containerRef$current.width,
        height = _containerRef$current.height;
      var offSetPercent;
      var removeDist;
      switch (direction) {
        case 'btt':
          offSetPercent = -offsetY / height;
          removeDist = offsetX;
          break;
        case 'ttb':
          offSetPercent = offsetY / height;
          removeDist = offsetX;
          break;
        case 'rtl':
          offSetPercent = -offsetX / width;
          removeDist = offsetY;
          break;
        default:
          offSetPercent = offsetX / width;
          removeDist = offsetY;
      }

      // Check if need mark remove
      deleteMark = editable ? Math.abs(removeDist) > REMOVE_DIST && minCount < cacheValues.length : false;
      setDraggingDelete(deleteMark);
      updateCacheValue(valueIndex, offSetPercent, deleteMark);
    };

    // End
    var onMouseUp = function onMouseUp(event) {
      event.preventDefault();
      document.removeEventListener('mouseup', onMouseUp);
      document.removeEventListener('mousemove', onMouseMove);
      if (touchEventTargetRef.current) {
        touchEventTargetRef.current.removeEventListener('touchmove', mouseMoveEventRef.current);
        touchEventTargetRef.current.removeEventListener('touchend', mouseUpEventRef.current);
      }
      mouseMoveEventRef.current = null;
      mouseUpEventRef.current = null;
      touchEventTargetRef.current = null;
      finishChange(deleteMark);
      setDraggingIndex(-1);
      setDraggingDelete(false);
    };
    document.addEventListener('mouseup', onMouseUp);
    document.addEventListener('mousemove', onMouseMove);
    e.currentTarget.addEventListener('touchend', onMouseUp);
    e.currentTarget.addEventListener('touchmove', onMouseMove);
    mouseMoveEventRef.current = onMouseMove;
    mouseUpEventRef.current = onMouseUp;
    touchEventTargetRef.current = e.currentTarget;
  };

  // Only return cache value when it mapping with rawValues
  var returnValues = React.useMemo(function () {
    var sourceValues = (0, _toConsumableArray2.default)(rawValues).sort(function (a, b) {
      return a - b;
    });
    var targetValues = (0, _toConsumableArray2.default)(cacheValues).sort(function (a, b) {
      return a - b;
    });
    var counts = {};
    targetValues.forEach(function (val) {
      counts[val] = (counts[val] || 0) + 1;
    });
    sourceValues.forEach(function (val) {
      counts[val] = (counts[val] || 0) - 1;
    });
    var maxDiffCount = editable ? 1 : 0;
    var diffCount = Object.values(counts).reduce(function (prev, next) {
      return prev + Math.abs(next);
    }, 0);
    return diffCount <= maxDiffCount ? cacheValues : rawValues;
  }, [rawValues, cacheValues, editable]);
  return [draggingIndex, draggingValue, draggingDelete, returnValues, onStartMove];
}
var _default = exports.default = useDrag;