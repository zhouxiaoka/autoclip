import * as React from 'react';
import type { Breakpoint } from '../_util/responsiveObserver';
declare const _RowAligns: readonly ["top", "middle", "bottom", "stretch"];
declare const _RowJustify: readonly ["start", "end", "center", "space-around", "space-between", "space-evenly"];
type Responsive = 'xxl' | 'xl' | 'lg' | 'md' | 'sm' | 'xs';
type ResponsiveLike<T> = {
    [key in Responsive]?: T;
};
export type Gutter = number | undefined | Partial<Record<Breakpoint, number>>;
type ResponsiveAligns = ResponsiveLike<(typeof _RowAligns)[number]>;
type ResponsiveJustify = ResponsiveLike<(typeof _RowJustify)[number]>;
export interface RowProps extends React.HTMLAttributes<HTMLDivElement> {
    gutter?: Gutter | [Gutter, Gutter];
    align?: (typeof _RowAligns)[number] | ResponsiveAligns;
    justify?: (typeof _RowJustify)[number] | ResponsiveJustify;
    prefixCls?: string;
    wrap?: boolean;
}
declare const Row: React.ForwardRefExoticComponent<RowProps & React.RefAttributes<HTMLDivElement>>;
export default Row;
