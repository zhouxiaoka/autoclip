"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useLockEffect;
var _useLayoutEffect = require("rc-util/lib/hooks/useLayoutEffect");
var _raf = _interopRequireDefault(require("rc-util/lib/raf"));
var React = _interopRequireWildcard(require("react"));
/**
 * Trigger `callback` immediately when `condition` is `true`.
 * But trigger `callback` in next frame when `condition` is `false`.
 */
function useLockEffect(condition, callback) {
  var delayFrames = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : 1;
  var callbackRef = React.useRef(callback);
  callbackRef.current = callback;
  (0, _useLayoutEffect.useLayoutUpdateEffect)(function () {
    if (condition) {
      callbackRef.current(condition);
    } else {
      var id = (0, _raf.default)(function () {
        callbackRef.current(condition);
      }, delayFrames);
      return function () {
        _raf.default.cancel(id);
      };
    }
  }, [condition]);
}