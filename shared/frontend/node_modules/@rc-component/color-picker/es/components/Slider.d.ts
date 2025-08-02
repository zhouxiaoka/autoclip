import type { FC } from 'react';
import type { HsbaColorType } from '../interface';
import { Color } from '../color';
export interface BaseSliderProps {
    prefixCls: string;
    colors: {
        percent: number;
        color: string;
    }[];
    min: number;
    max: number;
    value: number;
    disabled: boolean;
    onChange: (value: number) => void;
    onChangeComplete: (value: number) => void;
    type: HsbaColorType;
    color: Color;
}
declare const Slider: FC<BaseSliderProps>;
export default Slider;
