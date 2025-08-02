import type { FC } from 'react';
import type { AggregationColor } from '../color';
interface ColorClearProps {
    prefixCls: string;
    value?: AggregationColor;
    onChange?: (value: AggregationColor) => void;
}
declare const ColorClear: FC<ColorClearProps>;
export default ColorClear;
