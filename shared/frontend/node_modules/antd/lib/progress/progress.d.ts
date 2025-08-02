import * as React from 'react';
export declare const ProgressTypes: readonly ["line", "circle", "dashboard"];
export type ProgressType = (typeof ProgressTypes)[number];
declare const ProgressStatuses: readonly ["normal", "exception", "active", "success"];
export type ProgressSize = 'default' | 'small';
export type StringGradients = Record<string, string>;
type FromToGradients = {
    from: string;
    to: string;
};
export type ProgressGradient = {
    direction?: string;
} & (StringGradients | FromToGradients);
export interface PercentPositionType {
    align?: 'start' | 'center' | 'end';
    type?: 'inner' | 'outer';
}
export interface SuccessProps {
    percent?: number;
    /** @deprecated Use `percent` instead */
    progress?: number;
    strokeColor?: string;
}
export type ProgressAriaProps = Pick<React.AriaAttributes, 'aria-label' | 'aria-labelledby'>;
export interface ProgressProps extends ProgressAriaProps {
    prefixCls?: string;
    className?: string;
    rootClassName?: string;
    type?: ProgressType;
    percent?: number;
    format?: (percent?: number, successPercent?: number) => React.ReactNode;
    status?: (typeof ProgressStatuses)[number];
    showInfo?: boolean;
    strokeWidth?: number;
    strokeLinecap?: 'butt' | 'square' | 'round';
    strokeColor?: string | string[] | ProgressGradient;
    trailColor?: string;
    /** @deprecated Use `size` instead */
    width?: number;
    success?: SuccessProps;
    style?: React.CSSProperties;
    gapDegree?: number;
    gapPosition?: 'top' | 'bottom' | 'left' | 'right';
    size?: number | [number | string, number] | ProgressSize | {
        width?: number;
        height?: number;
    };
    steps?: number | {
        count: number;
        gap: number;
    };
    /** @deprecated Use `success` instead */
    successPercent?: number;
    percentPosition?: PercentPositionType;
    children?: React.ReactNode;
    rounding?: (step: number) => number;
}
declare const Progress: React.ForwardRefExoticComponent<ProgressProps & React.RefAttributes<HTMLDivElement>>;
export default Progress;
