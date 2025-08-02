import type { FC } from 'react';
import type { AggregationColor } from '../color';
interface ColorAlphaInputProps {
    prefixCls: string;
    value?: AggregationColor;
    onChange?: (value: AggregationColor) => void;
}
declare const ColorAlphaInput: FC<ColorAlphaInputProps>;
export default ColorAlphaInput;
