import * as React from 'react';
import useEvent from "rc-util/es/hooks/useEvent";
import useMergedState from "rc-util/es/hooks/useMergedState";
import { useLocale } from '../../locale';
import { generateColor } from '../util';
/**
 * Combine the `color` and `mode` to make sure sync of state.
 */
export default function useModeColor(defaultValue, value, mode) {
  const [locale] = useLocale('ColorPicker');
  // ======================== Base ========================
  // Color
  const [mergedColor, setMergedColor] = useMergedState(defaultValue, {
    value
  });
  // Mode
  const [modeState, setModeState] = React.useState('single');
  const [modeOptionList, modeSet] = React.useMemo(() => {
    const list = (Array.isArray(mode) ? mode : [mode]).filter(m => m);
    if (!list.length) {
      list.push('single');
    }
    const modes = new Set(list);
    const optionList = [];
    const pushOption = (modeType, localeTxt) => {
      if (modes.has(modeType)) {
        optionList.push({
          label: localeTxt,
          value: modeType
        });
      }
    };
    pushOption('single', locale.singleColor);
    pushOption('gradient', locale.gradientColor);
    return [optionList, modes];
  }, [mode]);
  // ======================== Post ========================
  // We need align `mode` with `color` state
  // >>>>> Color
  const [cacheColor, setCacheColor] = React.useState(null);
  const setColor = useEvent(nextColor => {
    setCacheColor(nextColor);
    setMergedColor(nextColor);
  });
  const postColor = React.useMemo(() => {
    const colorObj = generateColor(mergedColor || '');
    // Use `cacheColor` in case the color is `cleared`
    return colorObj.equals(cacheColor) ? cacheColor : colorObj;
  }, [mergedColor, cacheColor]);
  // >>>>> Mode
  const postMode = React.useMemo(() => {
    var _a;
    if (modeSet.has(modeState)) {
      return modeState;
    }
    return (_a = modeOptionList[0]) === null || _a === void 0 ? void 0 : _a.value;
  }, [modeSet, modeState, modeOptionList]);
  // ======================= Effect =======================
  // Dynamic update mode when color change
  React.useEffect(() => {
    setModeState(postColor.isGradient() ? 'gradient' : 'single');
  }, [postColor]);
  // ======================= Return =======================
  return [postColor, setColor, postMode, setModeState, modeOptionList];
}