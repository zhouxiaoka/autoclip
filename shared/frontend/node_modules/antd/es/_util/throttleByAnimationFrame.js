import _toConsumableArray from "@babel/runtime/helpers/esm/toConsumableArray";
import raf from "rc-util/es/raf";
function throttleByAnimationFrame(fn) {
  let requestId;
  const later = args => () => {
    requestId = null;
    fn.apply(void 0, _toConsumableArray(args));
  };
  const throttled = (...args) => {
    if (requestId == null) {
      requestId = raf(later(args));
    }
  };
  throttled.cancel = () => {
    raf.cancel(requestId);
    requestId = null;
  };
  return throttled;
}
export default throttleByAnimationFrame;