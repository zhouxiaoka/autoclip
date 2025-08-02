import * as React from 'react';
import type { RenderFunction } from '../_util/getRenderPropValue';
import type { AbstractTooltipProps, TooltipRef } from '../tooltip';
import PurePanel from './PurePanel';
export interface PopoverProps extends AbstractTooltipProps {
    title?: React.ReactNode | RenderFunction;
    content?: React.ReactNode | RenderFunction;
    onOpenChange?: (open: boolean, e?: React.MouseEvent<HTMLElement> | React.KeyboardEvent<HTMLDivElement>) => void;
}
declare const InternalPopover: React.ForwardRefExoticComponent<PopoverProps & React.RefAttributes<TooltipRef>>;
type CompoundedComponent = typeof InternalPopover & {
    _InternalPanelDoNotUseOrYouWillBeFired: typeof PurePanel;
};
declare const Popover: CompoundedComponent;
export default Popover;
