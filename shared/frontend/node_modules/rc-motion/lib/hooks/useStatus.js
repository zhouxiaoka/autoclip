"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
var _typeof = require("@babel/runtime/helpers/typeof");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useStatus;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _rcUtil = require("rc-util");
var _useState5 = _interopRequireDefault(require("rc-util/lib/hooks/useState"));
var _useSyncState3 = _interopRequireDefault(require("rc-util/lib/hooks/useSyncState"));
var _react = _interopRequireWildcard(require("react"));
var React = _react;
var _interface = require("../interface");
var _useDomMotionEvents3 = _interopRequireDefault(require("./useDomMotionEvents"));
var _useIsomorphicLayoutEffect = _interopRequireDefault(require("./useIsomorphicLayoutEffect"));
var _useStepQueue3 = _interopRequireWildcard(require("./useStepQueue"));
function _getRequireWildcardCache(e) { if ("function" != typeof WeakMap) return null; var r = new WeakMap(), t = new WeakMap(); return (_getRequireWildcardCache = function _getRequireWildcardCache(e) { return e ? t : r; })(e); }
function _interopRequireWildcard(e, r) { if (!r && e && e.__esModule) return e; if (null === e || "object" != _typeof(e) && "function" != typeof e) return { default: e }; var t = _getRequireWildcardCache(r); if (t && t.has(e)) return t.get(e); var n = { __proto__: null }, a = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var u in e) if ("default" !== u && Object.prototype.hasOwnProperty.call(e, u)) { var i = a ? Object.getOwnPropertyDescriptor(e, u) : null; i && (i.get || i.set) ? Object.defineProperty(n, u, i) : n[u] = e[u]; } return n.default = e, t && t.set(e, n), n; }
function useStatus(supportMotion, visible, getElement, _ref) {
  var _ref$motionEnter = _ref.motionEnter,
    motionEnter = _ref$motionEnter === void 0 ? true : _ref$motionEnter,
    _ref$motionAppear = _ref.motionAppear,
    motionAppear = _ref$motionAppear === void 0 ? true : _ref$motionAppear,
    _ref$motionLeave = _ref.motionLeave,
    motionLeave = _ref$motionLeave === void 0 ? true : _ref$motionLeave,
    motionDeadline = _ref.motionDeadline,
    motionLeaveImmediately = _ref.motionLeaveImmediately,
    onAppearPrepare = _ref.onAppearPrepare,
    onEnterPrepare = _ref.onEnterPrepare,
    onLeavePrepare = _ref.onLeavePrepare,
    onAppearStart = _ref.onAppearStart,
    onEnterStart = _ref.onEnterStart,
    onLeaveStart = _ref.onLeaveStart,
    onAppearActive = _ref.onAppearActive,
    onEnterActive = _ref.onEnterActive,
    onLeaveActive = _ref.onLeaveActive,
    onAppearEnd = _ref.onAppearEnd,
    onEnterEnd = _ref.onEnterEnd,
    onLeaveEnd = _ref.onLeaveEnd,
    onVisibleChanged = _ref.onVisibleChanged;
  // Used for outer render usage to avoid `visible: false & status: none` to render nothing
  var _useState = (0, _useState5.default)(),
    _useState2 = (0, _slicedToArray2.default)(_useState, 2),
    asyncVisible = _useState2[0],
    setAsyncVisible = _useState2[1];
  var _useSyncState = (0, _useSyncState3.default)(_interface.STATUS_NONE),
    _useSyncState2 = (0, _slicedToArray2.default)(_useSyncState, 2),
    getStatus = _useSyncState2[0],
    setStatus = _useSyncState2[1];
  var _useState3 = (0, _useState5.default)(null),
    _useState4 = (0, _slicedToArray2.default)(_useState3, 2),
    style = _useState4[0],
    setStyle = _useState4[1];
  var currentStatus = getStatus();
  var mountedRef = (0, _react.useRef)(false);
  var deadlineRef = (0, _react.useRef)(null);

  // =========================== Dom Node ===========================
  function getDomElement() {
    return getElement();
  }

  // ========================== Motion End ==========================
  var activeRef = (0, _react.useRef)(false);

  /**
   * Clean up status & style
   */
  function updateMotionEndStatus() {
    setStatus(_interface.STATUS_NONE);
    setStyle(null, true);
  }
  var onInternalMotionEnd = (0, _rcUtil.useEvent)(function (event) {
    var status = getStatus();
    // Do nothing since not in any transition status.
    // This may happen when `motionDeadline` trigger.
    if (status === _interface.STATUS_NONE) {
      return;
    }
    var element = getDomElement();
    if (event && !event.deadline && event.target !== element) {
      // event exists
      // not initiated by deadline
      // transitionEnd not fired by inner elements
      return;
    }
    var currentActive = activeRef.current;
    var canEnd;
    if (status === _interface.STATUS_APPEAR && currentActive) {
      canEnd = onAppearEnd === null || onAppearEnd === void 0 ? void 0 : onAppearEnd(element, event);
    } else if (status === _interface.STATUS_ENTER && currentActive) {
      canEnd = onEnterEnd === null || onEnterEnd === void 0 ? void 0 : onEnterEnd(element, event);
    } else if (status === _interface.STATUS_LEAVE && currentActive) {
      canEnd = onLeaveEnd === null || onLeaveEnd === void 0 ? void 0 : onLeaveEnd(element, event);
    }

    // Only update status when `canEnd` and not destroyed
    if (currentActive && canEnd !== false) {
      updateMotionEndStatus();
    }
  });
  var _useDomMotionEvents = (0, _useDomMotionEvents3.default)(onInternalMotionEnd),
    _useDomMotionEvents2 = (0, _slicedToArray2.default)(_useDomMotionEvents, 1),
    patchMotionEvents = _useDomMotionEvents2[0];

  // ============================= Step =============================
  var getEventHandlers = function getEventHandlers(targetStatus) {
    switch (targetStatus) {
      case _interface.STATUS_APPEAR:
        return (0, _defineProperty2.default)((0, _defineProperty2.default)((0, _defineProperty2.default)({}, _interface.STEP_PREPARE, onAppearPrepare), _interface.STEP_START, onAppearStart), _interface.STEP_ACTIVE, onAppearActive);
      case _interface.STATUS_ENTER:
        return (0, _defineProperty2.default)((0, _defineProperty2.default)((0, _defineProperty2.default)({}, _interface.STEP_PREPARE, onEnterPrepare), _interface.STEP_START, onEnterStart), _interface.STEP_ACTIVE, onEnterActive);
      case _interface.STATUS_LEAVE:
        return (0, _defineProperty2.default)((0, _defineProperty2.default)((0, _defineProperty2.default)({}, _interface.STEP_PREPARE, onLeavePrepare), _interface.STEP_START, onLeaveStart), _interface.STEP_ACTIVE, onLeaveActive);
      default:
        return {};
    }
  };
  var eventHandlers = React.useMemo(function () {
    return getEventHandlers(currentStatus);
  }, [currentStatus]);
  var _useStepQueue = (0, _useStepQueue3.default)(currentStatus, !supportMotion, function (newStep) {
      // Only prepare step can be skip
      if (newStep === _interface.STEP_PREPARE) {
        var onPrepare = eventHandlers[_interface.STEP_PREPARE];
        if (!onPrepare) {
          return _useStepQueue3.SkipStep;
        }
        return onPrepare(getDomElement());
      }

      // Rest step is sync update
      if (step in eventHandlers) {
        var _eventHandlers$step;
        setStyle(((_eventHandlers$step = eventHandlers[step]) === null || _eventHandlers$step === void 0 ? void 0 : _eventHandlers$step.call(eventHandlers, getDomElement(), null)) || null);
      }
      if (step === _interface.STEP_ACTIVE && currentStatus !== _interface.STATUS_NONE) {
        // Patch events when motion needed
        patchMotionEvents(getDomElement());
        if (motionDeadline > 0) {
          clearTimeout(deadlineRef.current);
          deadlineRef.current = setTimeout(function () {
            onInternalMotionEnd({
              deadline: true
            });
          }, motionDeadline);
        }
      }
      if (step === _interface.STEP_PREPARED) {
        updateMotionEndStatus();
      }
      return _useStepQueue3.DoStep;
    }),
    _useStepQueue2 = (0, _slicedToArray2.default)(_useStepQueue, 2),
    startStep = _useStepQueue2[0],
    step = _useStepQueue2[1];
  var active = (0, _useStepQueue3.isActive)(step);
  activeRef.current = active;

  // ============================ Status ============================
  var visibleRef = (0, _react.useRef)(null);

  // Update with new status
  (0, _useIsomorphicLayoutEffect.default)(function () {
    // When use Suspense, the `visible` will repeat trigger,
    // But not real change of the `visible`, we need to skip it.
    // https://github.com/ant-design/ant-design/issues/44379
    if (mountedRef.current && visibleRef.current === visible) {
      return;
    }
    setAsyncVisible(visible);
    var isMounted = mountedRef.current;
    mountedRef.current = true;

    // if (!supportMotion) {
    //   return;
    // }

    var nextStatus;

    // Appear
    if (!isMounted && visible && motionAppear) {
      nextStatus = _interface.STATUS_APPEAR;
    }

    // Enter
    if (isMounted && visible && motionEnter) {
      nextStatus = _interface.STATUS_ENTER;
    }

    // Leave
    if (isMounted && !visible && motionLeave || !isMounted && motionLeaveImmediately && !visible && motionLeave) {
      nextStatus = _interface.STATUS_LEAVE;
    }
    var nextEventHandlers = getEventHandlers(nextStatus);

    // Update to next status
    if (nextStatus && (supportMotion || nextEventHandlers[_interface.STEP_PREPARE])) {
      setStatus(nextStatus);
      startStep();
    } else {
      // Set back in case no motion but prev status has prepare step
      setStatus(_interface.STATUS_NONE);
    }
    visibleRef.current = visible;
  }, [visible]);

  // ============================ Effect ============================
  // Reset when motion changed
  (0, _react.useEffect)(function () {
    if (
    // Cancel appear
    currentStatus === _interface.STATUS_APPEAR && !motionAppear ||
    // Cancel enter
    currentStatus === _interface.STATUS_ENTER && !motionEnter ||
    // Cancel leave
    currentStatus === _interface.STATUS_LEAVE && !motionLeave) {
      setStatus(_interface.STATUS_NONE);
    }
  }, [motionAppear, motionEnter, motionLeave]);
  (0, _react.useEffect)(function () {
    return function () {
      mountedRef.current = false;
      clearTimeout(deadlineRef.current);
    };
  }, []);

  // Trigger `onVisibleChanged`
  var firstMountChangeRef = React.useRef(false);
  (0, _react.useEffect)(function () {
    // [visible & motion not end] => [!visible & motion end] still need trigger onVisibleChanged
    if (asyncVisible) {
      firstMountChangeRef.current = true;
    }
    if (asyncVisible !== undefined && currentStatus === _interface.STATUS_NONE) {
      // Skip first render is invisible since it's nothing changed
      if (firstMountChangeRef.current || asyncVisible) {
        onVisibleChanged === null || onVisibleChanged === void 0 || onVisibleChanged(asyncVisible);
      }
      firstMountChangeRef.current = true;
    }
  }, [asyncVisible, currentStatus]);

  // ============================ Styles ============================
  var mergedStyle = style;
  if (eventHandlers[_interface.STEP_PREPARE] && step === _interface.STEP_START) {
    mergedStyle = (0, _objectSpread2.default)({
      transition: 'none'
    }, mergedStyle);
  }
  return [currentStatus, step, mergedStyle, asyncVisible !== null && asyncVisible !== void 0 ? asyncVisible : visible];
}