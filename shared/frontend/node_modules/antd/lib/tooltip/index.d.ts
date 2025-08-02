import * as React from 'react';
import type { placements as Placements } from 'rc-tooltip/lib/placements';
import type { TooltipProps as RcTooltipProps } from 'rc-tooltip/lib/Tooltip';
import type { PresetColorType } from '../_util/colors';
import type { RenderFunction } from '../_util/getRenderPropValue';
import type { AdjustOverflow, PlacementsConfig } from '../_util/placements';
import type { LiteralUnion } from '../_util/type';
import PurePanel from './PurePanel';
export type { AdjustOverflow, PlacementsConfig };
export interface TooltipRef {
    /** @deprecated Please use `forceAlign` instead */
    forcePopupAlign: VoidFunction;
    forceAlign: VoidFunction;
    /** Wrapped dom element. Not promise valid if child not support ref */
    nativeElement: HTMLElement;
    /** Popup dom element */
    popupElement: HTMLDivElement;
}
export type TooltipPlacement = 'top' | 'left' | 'right' | 'bottom' | 'topLeft' | 'topRight' | 'bottomLeft' | 'bottomRight' | 'leftTop' | 'leftBottom' | 'rightTop' | 'rightBottom';
export interface TooltipAlignConfig {
    points?: [string, string];
    offset?: [number | string, number | string];
    targetOffset?: [number | string, number | string];
    overflow?: {
        adjustX: boolean;
        adjustY: boolean;
    };
    useCssRight?: boolean;
    useCssBottom?: boolean;
    useCssTransform?: boolean;
}
interface LegacyTooltipProps extends Partial<Omit<RcTooltipProps, 'children' | 'visible' | 'defaultVisible' | 'onVisibleChange' | 'afterVisibleChange' | 'destroyTooltipOnHide'>> {
    open?: RcTooltipProps['visible'];
    defaultOpen?: RcTooltipProps['defaultVisible'];
    onOpenChange?: RcTooltipProps['onVisibleChange'];
    afterOpenChange?: RcTooltipProps['afterVisibleChange'];
    /** @deprecated Please use `open` instead. */
    visible?: RcTooltipProps['visible'];
    /** @deprecated Please use `defaultOpen` instead. */
    defaultVisible?: RcTooltipProps['defaultVisible'];
    /** @deprecated Please use `onOpenChange` instead. */
    onVisibleChange?: RcTooltipProps['onVisibleChange'];
    /** @deprecated Please use `afterOpenChange` instead. */
    afterVisibleChange?: RcTooltipProps['afterVisibleChange'];
}
type SemanticName = 'root' | 'body';
export interface AbstractTooltipProps extends LegacyTooltipProps {
    styles?: Partial<Record<SemanticName, React.CSSProperties>>;
    classNames?: Partial<Record<SemanticName, string>>;
    style?: React.CSSProperties;
    className?: string;
    rootClassName?: string;
    color?: LiteralUnion<PresetColorType>;
    placement?: TooltipPlacement;
    builtinPlacements?: typeof Placements;
    openClassName?: string;
    /** @deprecated Please use `arrow={{ pointAtCenter: true }}` instead. */
    arrowPointAtCenter?: boolean;
    arrow?: boolean | {
        /** @deprecated Please use `pointAtCenter` instead. */
        arrowPointAtCenter?: boolean;
        pointAtCenter?: boolean;
    };
    autoAdjustOverflow?: boolean | AdjustOverflow;
    getPopupContainer?: (triggerNode: HTMLElement) => HTMLElement;
    children?: React.ReactNode;
    /** @deprecated Please use `destroyOnHidden` instead */
    destroyTooltipOnHide?: boolean | {
        keepParent?: boolean;
    };
    /**
     * @since 5.25.0
     */
    destroyOnHidden?: boolean;
}
export interface TooltipPropsWithOverlay extends AbstractTooltipProps {
    title?: React.ReactNode | RenderFunction;
    overlay?: React.ReactNode | RenderFunction;
}
export interface TooltipPropsWithTitle extends AbstractTooltipProps {
    title: React.ReactNode | RenderFunction;
    overlay?: React.ReactNode | RenderFunction;
}
export declare type TooltipProps = TooltipPropsWithTitle | TooltipPropsWithOverlay;
declare const InternalTooltip: React.ForwardRefExoticComponent<TooltipProps & React.RefAttributes<TooltipRef>>;
type CompoundedComponent = typeof InternalTooltip & {
    _InternalPanelDoNotUseOrYouWillBeFired: typeof PurePanel;
};
declare const Tooltip: CompoundedComponent;
export default Tooltip;
