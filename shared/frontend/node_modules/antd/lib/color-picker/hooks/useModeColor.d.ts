import * as React from 'react';
import type { AggregationColor } from '../color';
import type { ColorPickerProps, ColorValueType, ModeType } from '../interface';
export type ModeOptions = {
    label: React.ReactNode;
    value: ModeType;
}[];
/**
 * Combine the `color` and `mode` to make sure sync of state.
 */
export default function useModeColor(defaultValue?: ColorValueType, value?: ColorValueType, mode?: ColorPickerProps['mode']): [
    color: AggregationColor,
    setColor: (color: AggregationColor) => void,
    mode: ModeType,
    setMode: (mode: ModeType) => void,
    modeOptionList: ModeOptions
];
