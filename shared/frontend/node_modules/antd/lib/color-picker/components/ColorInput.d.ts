import type { FC } from 'react';
import type { AggregationColor } from '../color';
import type { ColorFormatType } from '../interface';
interface ColorInputProps {
    prefixCls: string;
    format?: ColorFormatType;
    onFormatChange?: (format: ColorFormatType) => void;
    disabledAlpha?: boolean;
    value?: AggregationColor;
    onChange?: (value: AggregationColor) => void;
    disabledFormat?: boolean;
}
declare const ColorInput: FC<ColorInputProps>;
export default ColorInput;
