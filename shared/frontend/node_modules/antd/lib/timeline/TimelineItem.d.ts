import * as React from 'react';
import type { LiteralUnion } from '../_util/type';
type Color = 'blue' | 'red' | 'green' | 'gray';
export interface TimelineItemProps {
    key?: React.Key;
    prefixCls?: string;
    className?: string;
    color?: LiteralUnion<Color>;
    dot?: React.ReactNode;
    pending?: boolean;
    position?: string;
    style?: React.CSSProperties;
    label?: React.ReactNode;
    children?: React.ReactNode;
}
/**
 * @deprecated Use {@link TimelineItemProps} instead.
 * @see https://github.com/ant-design/ant-design/pull/27001
 */
export type TimeLineItemProps = TimelineItemProps;
declare const TimelineItem: React.FC<TimelineItemProps>;
export default TimelineItem;
