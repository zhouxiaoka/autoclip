import * as React from 'react';
import type { DrawerProps as RCDrawerProps } from 'rc-drawer';
import type { ClosableType } from '../_util/hooks/useClosable';
export interface DrawerClassNames extends NonNullable<RCDrawerProps['classNames']> {
    header?: string;
    body?: string;
    footer?: string;
}
export interface DrawerStyles extends NonNullable<RCDrawerProps['styles']> {
    header?: React.CSSProperties;
    body?: React.CSSProperties;
    footer?: React.CSSProperties;
}
export interface DrawerPanelProps {
    prefixCls: string;
    title?: React.ReactNode;
    footer?: React.ReactNode;
    extra?: React.ReactNode;
    /**
     * Recommend to use closeIcon instead
     *
     * e.g.
     *
     * `<Drawer closeIcon={false} />`
     */
    closable?: ClosableType;
    closeIcon?: React.ReactNode;
    onClose?: RCDrawerProps['onClose'];
    children?: React.ReactNode;
    classNames?: DrawerClassNames;
    styles?: DrawerStyles;
    loading?: boolean;
    /** @deprecated Please use `styles.header` instead */
    headerStyle?: React.CSSProperties;
    /** @deprecated Please use `styles.body` instead */
    bodyStyle?: React.CSSProperties;
    /** @deprecated Please use `styles.footer` instead */
    footerStyle?: React.CSSProperties;
    /** @deprecated Please use `styles.wrapper` instead */
    contentWrapperStyle?: React.CSSProperties;
    /** @deprecated Please use `styles.mask` instead */
    maskStyle?: React.CSSProperties;
    /** @deprecated Please use `styles.content` instead */
    drawerStyle?: React.CSSProperties;
}
declare const DrawerPanel: React.FC<DrawerPanelProps>;
export default DrawerPanel;
