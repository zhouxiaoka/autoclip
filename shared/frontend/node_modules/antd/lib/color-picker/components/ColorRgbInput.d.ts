import type { FC } from 'react';
import type { AggregationColor } from '../color';
interface ColorRgbInputProps {
    prefixCls: string;
    value?: AggregationColor;
    onChange?: (value: AggregationColor) => void;
}
declare const ColorRgbInput: FC<ColorRgbInputProps>;
export default ColorRgbInput;
