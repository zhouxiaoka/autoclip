import * as React from 'react';
import raf from "rc-util/es/raf";
export default function useRafLock() {
  const [state, setState] = React.useState(false);
  const rafRef = React.useRef(null);
  const cleanup = () => {
    raf.cancel(rafRef.current);
  };
  const setDelayState = nextState => {
    cleanup();
    if (nextState) {
      setState(nextState);
    } else {
      rafRef.current = raf(() => {
        setState(nextState);
      });
    }
  };
  React.useEffect(() => cleanup, []);
  return [state, setDelayState];
}