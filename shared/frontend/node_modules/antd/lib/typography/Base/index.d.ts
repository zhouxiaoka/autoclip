import * as React from 'react';
import type { JSX } from 'react';
import type { AutoSizeType } from 'rc-textarea';
import type { TooltipProps } from '../../tooltip';
import type { TypographyProps } from '../Typography';
export type BaseType = 'secondary' | 'success' | 'warning' | 'danger';
export interface CopyConfig {
    text?: string | (() => string | Promise<string>);
    onCopy?: (event?: React.MouseEvent<HTMLButtonElement>) => void;
    icon?: React.ReactNode;
    tooltips?: React.ReactNode;
    format?: 'text/plain' | 'text/html';
    tabIndex?: number;
}
interface EditConfig {
    text?: string;
    editing?: boolean;
    icon?: React.ReactNode;
    tooltip?: React.ReactNode;
    onStart?: () => void;
    onChange?: (value: string) => void;
    onCancel?: () => void;
    onEnd?: () => void;
    maxLength?: number;
    autoSize?: boolean | AutoSizeType;
    triggerType?: ('icon' | 'text')[];
    enterIcon?: React.ReactNode;
    tabIndex?: number;
}
export interface EllipsisConfig {
    rows?: number;
    expandable?: boolean | 'collapsible';
    suffix?: string;
    symbol?: React.ReactNode | ((expanded: boolean) => React.ReactNode);
    defaultExpanded?: boolean;
    expanded?: boolean;
    onExpand?: (e: React.MouseEvent<HTMLElement, MouseEvent>, info: {
        expanded: boolean;
    }) => void;
    onEllipsis?: (ellipsis: boolean) => void;
    tooltip?: React.ReactNode | TooltipProps;
}
export interface BlockProps<C extends keyof JSX.IntrinsicElements = keyof JSX.IntrinsicElements> extends TypographyProps<C> {
    title?: string;
    editable?: boolean | EditConfig;
    copyable?: boolean | CopyConfig;
    type?: BaseType;
    disabled?: boolean;
    ellipsis?: boolean | EllipsisConfig;
    code?: boolean;
    mark?: boolean;
    underline?: boolean;
    delete?: boolean;
    strong?: boolean;
    keyboard?: boolean;
    italic?: boolean;
}
declare const Base: React.ForwardRefExoticComponent<BlockProps<keyof JSX.IntrinsicElements> & React.RefAttributes<HTMLElement>>;
export default Base;
