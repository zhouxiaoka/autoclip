import { useMemo } from 'react';
export default function useShowSizeChanger(showSizeChanger) {
  return useMemo(() => {
    if (typeof showSizeChanger === 'boolean') {
      return [showSizeChanger, {}];
    }
    if (showSizeChanger && typeof showSizeChanger === 'object') {
      return [true, showSizeChanger];
    }
    return [undefined, undefined];
  }, [showSizeChanger]);
}