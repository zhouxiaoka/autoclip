"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useBubbleLock;
var _react = _interopRequireDefault(require("react"));
var _raf = _interopRequireDefault(require("rc-util/lib/raf"));
/**
 * When click on the label,
 * the event will be stopped to prevent the label from being clicked twice.
 * label click -> input click -> label click again
 */
function useBubbleLock(onOriginInputClick) {
  const labelClickLockRef = _react.default.useRef(null);
  const clearLock = () => {
    _raf.default.cancel(labelClickLockRef.current);
    labelClickLockRef.current = null;
  };
  const onLabelClick = () => {
    clearLock();
    labelClickLockRef.current = (0, _raf.default)(() => {
      labelClickLockRef.current = null;
    });
  };
  const onInputClick = e => {
    if (labelClickLockRef.current) {
      e.stopPropagation();
      clearLock();
    }
    onOriginInputClick === null || onOriginInputClick === void 0 ? void 0 : onOriginInputClick(e);
  };
  return [onLabelClick, onInputClick];
}