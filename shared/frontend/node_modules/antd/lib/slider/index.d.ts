import React from 'react';
import type { SliderProps as RcSliderProps } from 'rc-slider';
import type { SliderRef } from 'rc-slider/lib/Slider';
import type { GetProp } from '../_util/type';
import type { AbstractTooltipProps, TooltipPlacement } from '../tooltip';
export type SliderMarks = RcSliderProps['marks'];
export type SemanticName = 'root' | 'tracks' | 'track' | 'rail' | 'handle';
export type SliderClassNames = Partial<Record<SemanticName, string>>;
export type SliderStyles = Partial<Record<SemanticName, React.CSSProperties>>;
export interface SliderProps extends RcSliderProps {
    classNames?: SliderClassNames;
    styles?: SliderStyles;
}
interface HandleGeneratorInfo {
    value?: number;
    dragging?: boolean;
    index: number;
}
export type HandleGeneratorFn = (config: {
    tooltipPrefixCls?: string;
    prefixCls?: string;
    info: HandleGeneratorInfo;
}) => React.ReactElement;
export type Formatter = ((value?: number) => React.ReactNode) | null;
export interface SliderTooltipProps extends AbstractTooltipProps {
    prefixCls?: string;
    open?: boolean;
    placement?: TooltipPlacement;
    getPopupContainer?: (triggerNode: HTMLElement) => HTMLElement;
    formatter?: Formatter;
    autoAdjustOverflow?: boolean;
}
export interface SliderBaseProps {
    prefixCls?: string;
    reverse?: boolean;
    min?: number;
    max?: number;
    step?: null | number;
    marks?: SliderMarks;
    dots?: boolean;
    included?: boolean;
    disabled?: boolean;
    keyboard?: boolean;
    vertical?: boolean;
    className?: string;
    rootClassName?: string;
    id?: string;
    style?: React.CSSProperties;
    tooltip?: SliderTooltipProps;
    autoFocus?: boolean;
    styles?: SliderProps['styles'];
    classNames?: SliderProps['classNames'];
    onFocus?: React.FocusEventHandler<HTMLDivElement>;
    onBlur?: React.FocusEventHandler<HTMLDivElement>;
    /** @deprecated `tooltipPrefixCls` is deprecated. Please use `tooltip.prefixCls` instead. */
    tooltipPrefixCls?: string;
    /** @deprecated `tipFormatter` is deprecated. Please use `tooltip.formatter` instead. */
    tipFormatter?: Formatter;
    /** @deprecated `tooltipVisible` is deprecated. Please use `tooltip.open` instead. */
    tooltipVisible?: boolean;
    /**
     * @deprecated `getTooltipPopupContainer` is deprecated. Please use `tooltip.getPopupContainer`
     *   instead.
     */
    getTooltipPopupContainer?: (triggerNode: HTMLElement) => HTMLElement;
    /** @deprecated `tooltipPlacement` is deprecated. Please use `tooltip.placement` instead. */
    tooltipPlacement?: TooltipPlacement;
    tabIndex?: SliderProps['tabIndex'];
    ariaLabelForHandle?: SliderProps['ariaLabelForHandle'];
    ariaLabelledByForHandle?: SliderProps['ariaLabelledByForHandle'];
    ariaRequired?: SliderProps['ariaRequired'];
    ariaValueTextFormatterForHandle?: SliderProps['ariaValueTextFormatterForHandle'];
}
export interface SliderSingleProps extends SliderBaseProps {
    range?: false;
    value?: number;
    defaultValue?: number;
    onChange?: (value: number) => void;
    /** @deprecated Please use `onChangeComplete` instead */
    onAfterChange?: (value: number) => void;
    onChangeComplete?: (value: number) => void;
    /** @deprecated Please use `styles.handle` instead */
    handleStyle?: React.CSSProperties;
    /** @deprecated Please use `styles.track` instead */
    trackStyle?: React.CSSProperties;
    /** @deprecated Please use `styles.rail` instead */
    railStyle?: React.CSSProperties;
}
export interface SliderRangeProps extends SliderBaseProps {
    range: true | SliderRange;
    value?: number[];
    defaultValue?: number[];
    onChange?: (value: number[]) => void;
    /** @deprecated Please use `onChangeComplete` instead */
    onAfterChange?: (value: number[]) => void;
    onChangeComplete?: (value: number[]) => void;
    /** @deprecated Please use `styles.handle` instead */
    handleStyle?: React.CSSProperties[];
    /** @deprecated Please use `styles.track` instead */
    trackStyle?: React.CSSProperties[];
    /** @deprecated Please use `styles.rail` instead */
    railStyle?: React.CSSProperties;
}
type SliderRange = Exclude<GetProp<RcSliderProps, 'range'>, boolean>;
export type Opens = {
    [index: number]: boolean;
};
declare const Slider: React.ForwardRefExoticComponent<(SliderSingleProps | SliderRangeProps) & React.RefAttributes<SliderRef>>;
export default Slider;
