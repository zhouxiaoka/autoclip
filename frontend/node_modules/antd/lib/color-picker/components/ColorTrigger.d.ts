import type { CSSProperties, MouseEventHandler } from 'react';
import React from 'react';
import type { AggregationColor } from '../color';
import type { ColorFormatType, ColorPickerProps } from '../interface';
export interface ColorTriggerProps {
    prefixCls: string;
    disabled?: boolean;
    format?: ColorFormatType;
    color: AggregationColor;
    open?: boolean;
    showText?: ColorPickerProps['showText'];
    className?: string;
    style?: CSSProperties;
    onClick?: MouseEventHandler<HTMLDivElement>;
    onMouseEnter?: MouseEventHandler<HTMLDivElement>;
    onMouseLeave?: MouseEventHandler<HTMLDivElement>;
    activeIndex: number;
}
declare const ColorTrigger: React.ForwardRefExoticComponent<ColorTriggerProps & React.RefAttributes<HTMLDivElement>>;
export default ColorTrigger;
