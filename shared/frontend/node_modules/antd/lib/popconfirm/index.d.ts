import * as React from 'react';
import type { RenderFunction } from '../_util/getRenderPropValue';
import type { ButtonProps, LegacyButtonType } from '../button/button';
import type { AbstractTooltipProps, TooltipRef } from '../tooltip';
import PurePanel from './PurePanel';
export interface PopconfirmProps extends AbstractTooltipProps {
    title: React.ReactNode | RenderFunction;
    description?: React.ReactNode | RenderFunction;
    disabled?: boolean;
    onConfirm?: (e?: React.MouseEvent<HTMLElement>) => void;
    onCancel?: (e?: React.MouseEvent<HTMLElement>) => void;
    okText?: React.ReactNode;
    okType?: LegacyButtonType;
    cancelText?: React.ReactNode;
    okButtonProps?: ButtonProps;
    cancelButtonProps?: ButtonProps;
    showCancel?: boolean;
    icon?: React.ReactNode;
    onOpenChange?: (open: boolean, e?: React.MouseEvent<HTMLElement> | React.KeyboardEvent<HTMLDivElement>) => void;
    onPopupClick?: (e: React.MouseEvent<HTMLElement>) => void;
}
export interface PopconfirmState {
    open?: boolean;
}
declare const InternalPopconfirm: React.ForwardRefExoticComponent<PopconfirmProps & React.RefAttributes<TooltipRef>>;
type CompoundedComponent = typeof InternalPopconfirm & {
    _InternalPanelDoNotUseOrYouWillBeFired: typeof PurePanel;
};
declare const Popconfirm: CompoundedComponent;
export default Popconfirm;
