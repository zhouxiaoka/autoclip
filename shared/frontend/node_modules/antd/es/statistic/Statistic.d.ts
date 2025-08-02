import * as React from 'react';
import type { HTMLAriaDataAttributes } from '../_util/aria-data-attrs';
import type { FormatConfig, valueType } from './utils';
export interface StatisticRef {
    nativeElement: HTMLDivElement;
}
interface StatisticReactProps extends FormatConfig {
    prefixCls?: string;
    className?: string;
    rootClassName?: string;
    style?: React.CSSProperties;
    value?: valueType;
    valueStyle?: React.CSSProperties;
    valueRender?: (node: React.ReactNode) => React.ReactNode;
    title?: React.ReactNode;
    prefix?: React.ReactNode;
    suffix?: React.ReactNode;
    loading?: boolean;
    onMouseEnter?: React.MouseEventHandler<HTMLDivElement>;
    onMouseLeave?: React.MouseEventHandler<HTMLDivElement>;
}
export type StatisticProps = HTMLAriaDataAttributes & StatisticReactProps;
declare const Statistic: React.ForwardRefExoticComponent<React.AriaAttributes & {
    [key: `data-${string}`]: unknown;
} & Pick<React.HTMLAttributes<HTMLDivElement>, "role"> & StatisticReactProps & React.RefAttributes<StatisticRef>>;
export default Statistic;
