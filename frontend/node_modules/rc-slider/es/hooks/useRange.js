import { warning } from "rc-util/es/warning";
import { useMemo } from 'react';
export default function useRange(range) {
  return useMemo(function () {
    if (range === true || !range) {
      return [!!range, false, false, 0];
    }
    var editable = range.editable,
      draggableTrack = range.draggableTrack,
      minCount = range.minCount,
      maxCount = range.maxCount;
    if (process.env.NODE_ENV !== 'production') {
      warning(!editable || !draggableTrack, '`editable` can not work with `draggableTrack`.');
    }
    return [true, editable, !editable && draggableTrack, minCount || 0, maxCount];
  }, [range]);
}