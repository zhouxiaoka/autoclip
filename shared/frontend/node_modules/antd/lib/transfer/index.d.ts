import type { CSSProperties } from 'react';
import React from 'react';
import type { InputStatus } from '../_util/statusUtils';
import type { PaginationType, TransferKey } from './interface';
import type { TransferCustomListBodyProps, TransferListProps } from './list';
export type { TransferListProps } from './list';
export type { TransferOperationProps } from './operation';
export type { TransferSearchProps } from './search';
export type TransferDirection = 'left' | 'right';
export interface RenderResultObject {
    label: React.ReactElement;
    value: string;
}
export type RenderResult = React.ReactElement | RenderResultObject | string | null;
export interface TransferItem {
    key?: TransferKey;
    title?: string;
    description?: string;
    disabled?: boolean;
    [name: string]: any;
}
export type KeyWise<T> = T & {
    key: TransferKey;
};
export type KeyWiseTransferItem = KeyWise<TransferItem>;
type TransferRender<RecordType> = (item: RecordType) => RenderResult;
export interface ListStyle {
    direction: TransferDirection;
}
export type SelectAllLabel = React.ReactNode | ((info: {
    selectedCount: number;
    totalCount: number;
}) => React.ReactNode);
export interface TransferLocale {
    titles?: React.ReactNode[];
    notFoundContent?: React.ReactNode | React.ReactNode[];
    searchPlaceholder: string;
    itemUnit: string;
    itemsUnit: string;
    remove?: string;
    selectAll?: string;
    deselectAll?: string;
    selectCurrent?: string;
    selectInvert?: string;
    removeAll?: string;
    removeCurrent?: string;
}
export interface TransferSearchOption {
    placeholder?: string;
    defaultValue?: string;
}
export interface TransferProps<RecordType = any> {
    prefixCls?: string;
    className?: string;
    rootClassName?: string;
    disabled?: boolean;
    dataSource?: RecordType[];
    targetKeys?: TransferKey[];
    selectedKeys?: TransferKey[];
    render?: TransferRender<RecordType>;
    onChange?: (targetKeys: TransferKey[], direction: TransferDirection, moveKeys: TransferKey[]) => void;
    onSelectChange?: (sourceSelectedKeys: TransferKey[], targetSelectedKeys: TransferKey[]) => void;
    style?: React.CSSProperties;
    listStyle?: ((style: ListStyle) => CSSProperties) | CSSProperties;
    operationStyle?: CSSProperties;
    titles?: React.ReactNode[];
    operations?: string[];
    showSearch?: boolean | TransferSearchOption;
    filterOption?: (inputValue: string, item: RecordType, direction: TransferDirection) => boolean;
    locale?: Partial<TransferLocale>;
    footer?: (props: TransferListProps<RecordType>, info?: {
        direction: TransferDirection;
    }) => React.ReactNode;
    rowKey?: (record: RecordType) => TransferKey;
    onSearch?: (direction: TransferDirection, value: string) => void;
    onScroll?: (direction: TransferDirection, e: React.SyntheticEvent<HTMLUListElement>) => void;
    children?: (props: TransferCustomListBodyProps<RecordType>) => React.ReactNode;
    showSelectAll?: boolean;
    selectAllLabels?: SelectAllLabel[];
    oneWay?: boolean;
    pagination?: PaginationType;
    status?: InputStatus;
    selectionsIcon?: React.ReactNode;
}
declare const Transfer: {
    <RecordType extends TransferItem = TransferItem>(props: TransferProps<RecordType>): React.ReactElement<unknown, string | React.JSXElementConstructor<any>>;
    displayName: string;
    List: {
        <RecordType extends KeyWiseTransferItem>(props: TransferListProps<RecordType>): React.JSX.Element;
        displayName: string;
    };
    Search: React.FC<import("./search").TransferSearchProps>;
    Operation: React.FC<import("./operation").TransferOperationProps>;
};
export default Transfer;
