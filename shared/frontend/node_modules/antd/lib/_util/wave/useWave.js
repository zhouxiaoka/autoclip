"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _useEvent = _interopRequireDefault(require("rc-util/lib/hooks/useEvent"));
var _raf = _interopRequireDefault(require("rc-util/lib/raf"));
var _configProvider = require("../../config-provider");
var _useToken = _interopRequireDefault(require("../../theme/useToken"));
var _interface = require("./interface");
var _WaveEffect = _interopRequireDefault(require("./WaveEffect"));
const useWave = (nodeRef, className, component) => {
  const {
    wave
  } = React.useContext(_configProvider.ConfigContext);
  const [, token, hashId] = (0, _useToken.default)();
  const showWave = (0, _useEvent.default)(event => {
    const node = nodeRef.current;
    if ((wave === null || wave === void 0 ? void 0 : wave.disabled) || !node) {
      return;
    }
    const targetNode = node.querySelector(`.${_interface.TARGET_CLS}`) || node;
    const {
      showEffect
    } = wave || {};
    // Customize wave effect
    (showEffect || _WaveEffect.default)(targetNode, {
      className,
      token,
      component,
      event,
      hashId
    });
  });
  const rafId = React.useRef(null);
  // Merge trigger event into one for each frame
  const showDebounceWave = event => {
    _raf.default.cancel(rafId.current);
    rafId.current = (0, _raf.default)(() => {
      showWave(event);
    });
  };
  return showDebounceWave;
};
var _default = exports.default = useWave;