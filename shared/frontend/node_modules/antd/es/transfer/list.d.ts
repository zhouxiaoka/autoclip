import React from 'react';
import type { KeyWiseTransferItem, RenderResult, SelectAllLabel, TransferDirection, TransferLocale, TransferSearchOption } from './index';
import type { PaginationType, TransferKey } from './interface';
import type { TransferListBodyProps } from './ListBody';
export interface RenderedItem<RecordType> {
    renderedText: string;
    renderedEl: React.ReactNode;
    item: RecordType;
}
type RenderListFunction<T> = (props: TransferListBodyProps<T>) => React.ReactNode;
export interface TransferListProps<RecordType> extends TransferLocale {
    prefixCls: string;
    titleText: React.ReactNode;
    dataSource: RecordType[];
    filterOption?: (filterText: string, item: RecordType, direction: TransferDirection) => boolean;
    style?: React.CSSProperties;
    checkedKeys: TransferKey[];
    handleFilter: (e: React.ChangeEvent<HTMLInputElement>) => void;
    onItemSelect: (key: TransferKey, check: boolean, e?: React.MouseEvent<Element, MouseEvent>) => void;
    onItemSelectAll: (dataSource: TransferKey[], checkAll: boolean | 'replace') => void;
    onItemRemove?: (keys: TransferKey[]) => void;
    handleClear: () => void;
    /** Render item */
    render?: (item: RecordType) => RenderResult;
    showSearch?: boolean | TransferSearchOption;
    searchPlaceholder: string;
    itemUnit: string;
    itemsUnit: string;
    renderList?: RenderListFunction<RecordType>;
    footer?: (props: TransferListProps<RecordType>, info?: {
        direction: TransferDirection;
    }) => React.ReactNode;
    onScroll: (e: React.UIEvent<HTMLUListElement, UIEvent>) => void;
    disabled?: boolean;
    direction: TransferDirection;
    showSelectAll?: boolean;
    selectAllLabel?: SelectAllLabel;
    showRemove?: boolean;
    pagination?: PaginationType;
    selectionsIcon?: React.ReactNode;
}
export interface TransferCustomListBodyProps<T> extends TransferListBodyProps<T> {
}
declare const TransferList: {
    <RecordType extends KeyWiseTransferItem>(props: TransferListProps<RecordType>): React.JSX.Element;
    displayName: string;
};
export default TransferList;
