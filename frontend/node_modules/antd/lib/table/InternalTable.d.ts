import type { TableProps as RcTableProps } from 'rc-table';
import type { AnyObject } from '../_util/type';
import type { SizeType } from '../config-provider/SizeContext';
import type { SpinProps } from '../spin';
import type { ColumnsType, FilterValue, GetPopupContainer, RefInternalTable, SorterResult, SorterTooltipProps, SortOrder, TableCurrentDataSource, TableLocale, TablePaginationConfig, TableRowSelection } from './interface';
export type { ColumnsType, TablePaginationConfig };
export interface TableProps<RecordType = AnyObject> extends Omit<RcTableProps<RecordType>, 'transformColumns' | 'internalHooks' | 'internalRefs' | 'data' | 'columns' | 'scroll' | 'emptyText'> {
    dropdownPrefixCls?: string;
    dataSource?: RcTableProps<RecordType>['data'];
    columns?: ColumnsType<RecordType>;
    pagination?: false | TablePaginationConfig;
    loading?: boolean | SpinProps;
    size?: SizeType;
    bordered?: boolean;
    locale?: TableLocale;
    rootClassName?: string;
    onChange?: (pagination: TablePaginationConfig, filters: Record<string, FilterValue | null>, sorter: SorterResult<RecordType> | SorterResult<RecordType>[], extra: TableCurrentDataSource<RecordType>) => void;
    rowSelection?: TableRowSelection<RecordType>;
    getPopupContainer?: GetPopupContainer;
    scroll?: RcTableProps<RecordType>['scroll'] & {
        scrollToFirstRowOnChange?: boolean;
    };
    sortDirections?: SortOrder[];
    showSorterTooltip?: boolean | SorterTooltipProps;
    virtual?: boolean;
}
/** Same as `TableProps` but we need record parent render times */
export interface InternalTableProps<RecordType = AnyObject> extends TableProps<RecordType> {
    _renderTimes: number;
}
declare const _default: RefInternalTable;
export default _default;
