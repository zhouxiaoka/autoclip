import * as React from 'react';
import type { Tab } from 'rc-tabs/lib/interface';
import type { TabsProps } from '../tabs';
export type CardType = 'inner';
export type CardSize = 'default' | 'small';
export interface CardTabListType extends Omit<Tab, 'label'> {
    key: string;
    /** @deprecated Please use `label` instead */
    tab?: React.ReactNode;
    label?: React.ReactNode;
}
type SemanticName = 'header' | 'body' | 'extra' | 'actions' | 'title' | 'cover';
export interface CardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
    prefixCls?: string;
    title?: React.ReactNode;
    extra?: React.ReactNode;
    /** @deprecated Please use `variant` instead */
    bordered?: boolean;
    /** @deprecated Please use `styles.header` instead */
    headStyle?: React.CSSProperties;
    /** @deprecated Please use `styles.body` instead */
    bodyStyle?: React.CSSProperties;
    style?: React.CSSProperties;
    loading?: boolean;
    hoverable?: boolean;
    children?: React.ReactNode;
    id?: string;
    className?: string;
    rootClassName?: string;
    size?: CardSize;
    type?: CardType;
    cover?: React.ReactNode;
    actions?: React.ReactNode[];
    tabList?: CardTabListType[];
    tabBarExtraContent?: React.ReactNode;
    onTabChange?: (key: string) => void;
    activeTabKey?: string;
    defaultActiveTabKey?: string;
    tabProps?: TabsProps;
    classNames?: Partial<Record<SemanticName, string>>;
    styles?: Partial<Record<SemanticName, React.CSSProperties>>;
    variant?: 'borderless' | 'outlined';
}
declare const Card: React.ForwardRefExoticComponent<CardProps & React.RefAttributes<HTMLDivElement>>;
export default Card;
