import type { ArrowType, TriggerProps, TriggerRef } from '@rc-component/trigger';
import type { ActionType, AlignType, AnimationType } from '@rc-component/trigger/lib/interface';
import * as React from 'react';
export interface TooltipProps extends Pick<TriggerProps, 'onPopupAlign' | 'builtinPlacements' | 'fresh' | 'children' | 'mouseLeaveDelay' | 'mouseEnterDelay' | 'prefixCls' | 'forceRender' | 'popupVisible'> {
    trigger?: ActionType | ActionType[];
    defaultVisible?: boolean;
    visible?: boolean;
    placement?: string;
    /** @deprecated Use `motion` instead */
    transitionName?: string;
    /** @deprecated Use `motion` instead */
    animation?: AnimationType;
    /** Config popup motion */
    motion?: TriggerProps['popupMotion'];
    onVisibleChange?: (visible: boolean) => void;
    afterVisibleChange?: (visible: boolean) => void;
    overlay: (() => React.ReactNode) | React.ReactNode;
    /** @deprecated Please use `styles={{ root: {} }}` */
    overlayStyle?: React.CSSProperties;
    /** @deprecated Please use `classNames={{ root: {} }}` */
    overlayClassName?: string;
    getTooltipContainer?: (node: HTMLElement) => HTMLElement;
    destroyTooltipOnHide?: boolean;
    align?: AlignType;
    showArrow?: boolean | ArrowType;
    arrowContent?: React.ReactNode;
    id?: string;
    /** @deprecated Please use `styles={{ body: {} }}` */
    overlayInnerStyle?: React.CSSProperties;
    zIndex?: number;
    styles?: TooltipStyles;
    classNames?: TooltipClassNames;
}
export interface TooltipStyles {
    root?: React.CSSProperties;
    body?: React.CSSProperties;
}
export interface TooltipClassNames {
    root?: string;
    body?: string;
}
export interface TooltipRef extends TriggerRef {
}
declare const _default: React.ForwardRefExoticComponent<TooltipProps & React.RefAttributes<TooltipRef>>;
export default _default;
