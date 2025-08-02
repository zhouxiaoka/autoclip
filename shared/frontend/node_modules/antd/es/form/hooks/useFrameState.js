import * as React from 'react';
import raf from "rc-util/es/raf";
export default function useFrameState(defaultValue) {
  const [value, setValue] = React.useState(defaultValue);
  const frameRef = React.useRef(null);
  const batchRef = React.useRef([]);
  const destroyRef = React.useRef(false);
  React.useEffect(() => {
    destroyRef.current = false;
    return () => {
      destroyRef.current = true;
      raf.cancel(frameRef.current);
      frameRef.current = null;
    };
  }, []);
  function setFrameValue(updater) {
    if (destroyRef.current) {
      return;
    }
    if (frameRef.current === null) {
      batchRef.current = [];
      frameRef.current = raf(() => {
        frameRef.current = null;
        setValue(prevValue => {
          let current = prevValue;
          batchRef.current.forEach(func => {
            current = func(current);
          });
          return current;
        });
      });
    }
    batchRef.current.push(updater);
  }
  return [value, setFrameValue];
}