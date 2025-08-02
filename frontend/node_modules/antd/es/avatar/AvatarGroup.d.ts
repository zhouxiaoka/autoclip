import * as React from 'react';
import type { PopoverProps } from '../popover';
import type { AvatarSize } from './AvatarContext';
export interface AvatarGroupProps {
    className?: string;
    rootClassName?: string;
    children?: React.ReactNode;
    style?: React.CSSProperties;
    prefixCls?: string;
    /** @deprecated Please use `max={{ count: number }}` */
    maxCount?: number;
    /** @deprecated Please use `max={{ style: CSSProperties }}` */
    maxStyle?: React.CSSProperties;
    /** @deprecated Please use `max={{ popover: PopoverProps }}` */
    maxPopoverPlacement?: 'top' | 'bottom';
    /** @deprecated Please use `max={{ popover: PopoverProps }}` */
    maxPopoverTrigger?: 'hover' | 'focus' | 'click';
    max?: {
        count?: number;
        style?: React.CSSProperties;
        popover?: PopoverProps;
    };
    size?: AvatarSize;
    shape?: 'circle' | 'square';
}
declare const AvatarGroup: React.FC<AvatarGroupProps>;
export default AvatarGroup;
