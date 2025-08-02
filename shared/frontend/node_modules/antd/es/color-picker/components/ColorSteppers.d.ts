import type { FC } from 'react';
import React from 'react';
import type { InputNumberProps } from '../../input-number';
interface ColorSteppersProps {
    prefixCls: string;
    value?: number;
    min?: number;
    max?: number;
    onChange?: (value: number | null) => void;
    className?: string;
    prefix?: (prefixCls: string) => React.ReactNode;
    formatter?: InputNumberProps<number>['formatter'];
}
declare const ColorSteppers: FC<ColorSteppersProps>;
export default ColorSteppers;
