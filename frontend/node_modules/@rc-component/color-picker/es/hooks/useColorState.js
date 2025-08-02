import _slicedToArray from "@babel/runtime/helpers/esm/slicedToArray";
import { useMergedState } from 'rc-util';
import { useMemo } from 'react';
import { generateColor } from "../util";
var useColorState = function useColorState(defaultValue, value) {
  var _useMergedState = useMergedState(defaultValue, {
      value: value
    }),
    _useMergedState2 = _slicedToArray(_useMergedState, 2),
    mergedValue = _useMergedState2[0],
    setValue = _useMergedState2[1];
  var color = useMemo(function () {
    return generateColor(mergedValue);
  }, [mergedValue]);
  return [color, setValue];
};
export default useColorState;