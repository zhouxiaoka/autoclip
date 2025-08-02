import * as React from 'react';
import type { AlignType } from '@rc-component/trigger';
import type { AdjustOverflow } from '../_util/placements';
import type { MenuProps } from '../menu';
declare const _Placements: readonly ["topLeft", "topCenter", "topRight", "bottomLeft", "bottomCenter", "bottomRight", "top", "bottom"];
type Placement = (typeof _Placements)[number];
type OverlayFunc = () => React.ReactElement;
export type DropdownArrowOptions = {
    pointAtCenter?: boolean;
};
export interface DropdownProps {
    menu?: MenuProps;
    autoFocus?: boolean;
    arrow?: boolean | DropdownArrowOptions;
    trigger?: ('click' | 'hover' | 'contextMenu')[];
    /** @deprecated Please use `popupRender` instead */
    dropdownRender?: (originNode: React.ReactNode) => React.ReactNode;
    popupRender?: (originNode: React.ReactNode) => React.ReactNode;
    onOpenChange?: (open: boolean, info: {
        source: 'trigger' | 'menu';
    }) => void;
    open?: boolean;
    disabled?: boolean;
    /** @deprecated Please use `destroyOnHidden` instead */
    destroyPopupOnHide?: boolean;
    /**
     * @since 5.25.0
     */
    destroyOnHidden?: boolean;
    align?: AlignType;
    getPopupContainer?: (triggerNode: HTMLElement) => HTMLElement;
    prefixCls?: string;
    className?: string;
    rootClassName?: string;
    transitionName?: string;
    placement?: Placement;
    overlayClassName?: string;
    overlayStyle?: React.CSSProperties;
    forceRender?: boolean;
    mouseEnterDelay?: number;
    mouseLeaveDelay?: number;
    openClassName?: string;
    children?: React.ReactNode;
    autoAdjustOverflow?: boolean | AdjustOverflow;
    /** @deprecated Please use `menu` instead */
    overlay?: React.ReactElement | OverlayFunc;
    /** @deprecated Please use `open` instead */
    visible?: boolean;
    /** @deprecated Please use `onOpenChange` instead */
    onVisibleChange?: (open: boolean) => void;
}
type CompoundedComponent = React.FC<DropdownProps> & {
    _InternalPanelDoNotUseOrYouWillBeFired: typeof WrapPurePanel;
};
declare const Dropdown: CompoundedComponent;
declare const WrapPurePanel: React.FC<DropdownProps>;
export default Dropdown;
