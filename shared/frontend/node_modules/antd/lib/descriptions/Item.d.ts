import type * as React from 'react';
import type { Breakpoint } from '../_util/responsiveObserver';
type SemanticName = 'label' | 'content';
export interface DescriptionsItemProps {
    prefixCls?: string;
    className?: string;
    style?: React.CSSProperties;
    label?: React.ReactNode;
    /** @deprecated Please use `styles={{ label: {} }}` instead */
    labelStyle?: React.CSSProperties;
    /** @deprecated Please use `styles={{ content: {} }}` instead */
    contentStyle?: React.CSSProperties;
    styles?: Partial<Record<SemanticName, React.CSSProperties>>;
    classNames?: Partial<Record<SemanticName, string>>;
    children: React.ReactNode;
    span?: number | 'filled' | {
        [key in Breakpoint]?: number;
    };
}
declare const DescriptionsItem: React.FC<DescriptionsItemProps>;
export default DescriptionsItem;
