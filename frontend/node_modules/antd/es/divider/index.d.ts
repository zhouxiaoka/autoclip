import * as React from 'react';
import { SizeType } from '../config-provider/SizeContext';
export interface DividerProps {
    prefixCls?: string;
    type?: 'horizontal' | 'vertical';
    /**
     * @default center
     */
    orientation?: 'left' | 'right' | 'center' | 'start' | 'end';
    orientationMargin?: string | number;
    className?: string;
    rootClassName?: string;
    children?: React.ReactNode;
    dashed?: boolean;
    /**
     * @since 5.20.0
     * @default solid
     */
    variant?: 'dashed' | 'dotted' | 'solid';
    style?: React.CSSProperties;
    size?: SizeType;
    plain?: boolean;
}
declare const Divider: React.FC<DividerProps>;
export default Divider;
