import type { FC } from 'react';
import type { AggregationColor } from '../color';
interface ColorHsbInputProps {
    prefixCls: string;
    value?: AggregationColor;
    onChange?: (value: AggregationColor) => void;
}
declare const ColorHsbInput: FC<ColorHsbInputProps>;
export default ColorHsbInput;
