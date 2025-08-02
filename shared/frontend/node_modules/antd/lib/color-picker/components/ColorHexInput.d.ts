import type { FC } from 'react';
import type { AggregationColor } from '../color';
interface ColorHexInputProps {
    prefixCls: string;
    value?: AggregationColor;
    onChange?: (value: AggregationColor) => void;
}
declare const ColorHexInput: FC<ColorHexInputProps>;
export default ColorHexInput;
