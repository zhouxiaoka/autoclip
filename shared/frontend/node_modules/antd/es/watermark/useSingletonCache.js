import * as React from 'react';
import isEqual from "rc-util/es/isEqual";
/**
 * Singleton cache will only take latest `cacheParams` as key
 * and return the result for callback matching.
 */
export default function useSingletonCache() {
  const cacheRef = React.useRef([null, null]);
  const getCache = (cacheKeys, callback) => {
    const filteredKeys = cacheKeys.map(item => item instanceof HTMLElement || Number.isNaN(item) ? '' : item);
    if (!isEqual(cacheRef.current[0], filteredKeys)) {
      cacheRef.current = [filteredKeys, callback()];
    }
    return cacheRef.current[1];
  };
  return getCache;
}