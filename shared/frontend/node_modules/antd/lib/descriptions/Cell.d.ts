import * as React from 'react';
import type { SemanticName } from './DescriptionsContext';
export interface CellProps {
    itemPrefixCls: string;
    span: number;
    className?: string;
    component: string;
    style?: React.CSSProperties;
    /** @deprecated Please use `styles={{ label: {} }}` instead */
    labelStyle?: React.CSSProperties;
    /** @deprecated Please use `styles={{ content: {} }}` instead */
    contentStyle?: React.CSSProperties;
    styles?: Partial<Record<SemanticName, React.CSSProperties>>;
    classNames?: Partial<Record<SemanticName, string>>;
    bordered?: boolean;
    label?: React.ReactNode;
    content?: React.ReactNode;
    colon?: boolean;
    type?: 'label' | 'content' | 'item';
}
declare const Cell: React.FC<CellProps>;
export default Cell;
