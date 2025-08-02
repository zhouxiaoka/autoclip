import type { ReactNode } from 'react';
import * as React from 'react';
type RenderNode = React.ReactNode | ((props: any) => React.ReactNode);
export default function useIcons({ suffixIcon, clearIcon, menuItemSelectedIcon, removeIcon, loading, multiple, hasFeedback, prefixCls, showSuffixIcon, feedbackIcon, showArrow, componentName, }: {
    suffixIcon?: React.ReactNode;
    clearIcon?: RenderNode;
    menuItemSelectedIcon?: RenderNode;
    removeIcon?: RenderNode;
    loading?: boolean;
    multiple?: boolean;
    hasFeedback?: boolean;
    feedbackIcon?: ReactNode;
    prefixCls: string;
    showSuffixIcon?: boolean;
    showArrow?: boolean;
    componentName: string;
}): {
    clearIcon: string | number | bigint | boolean | Iterable<ReactNode> | Promise<string | number | bigint | boolean | React.ReactPortal | React.ReactElement<unknown, string | React.JSXElementConstructor<any>> | Iterable<ReactNode> | null | undefined> | React.JSX.Element | ((props: any) => React.ReactNode);
    suffixIcon: React.JSX.Element | (({ open, showSearch }: {
        open: boolean;
        showSearch: boolean;
    }) => React.JSX.Element | null) | null;
    itemIcon: string | number | bigint | boolean | Iterable<ReactNode> | Promise<string | number | bigint | boolean | React.ReactPortal | React.ReactElement<unknown, string | React.JSXElementConstructor<any>> | Iterable<ReactNode> | null | undefined> | React.JSX.Element | ((props: any) => React.ReactNode) | null;
    removeIcon: string | number | bigint | boolean | Iterable<ReactNode> | Promise<string | number | bigint | boolean | React.ReactPortal | React.ReactElement<unknown, string | React.JSXElementConstructor<any>> | Iterable<ReactNode> | null | undefined> | React.JSX.Element | ((props: any) => React.ReactNode) | null;
};
export {};
