"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useRafLock;
var React = _interopRequireWildcard(require("react"));
var _raf = _interopRequireDefault(require("rc-util/lib/raf"));
function useRafLock() {
  const [state, setState] = React.useState(false);
  const rafRef = React.useRef(null);
  const cleanup = () => {
    _raf.default.cancel(rafRef.current);
  };
  const setDelayState = nextState => {
    cleanup();
    if (nextState) {
      setState(nextState);
    } else {
      rafRef.current = (0, _raf.default)(() => {
        setState(nextState);
      });
    }
  };
  React.useEffect(() => cleanup, []);
  return [state, setDelayState];
}