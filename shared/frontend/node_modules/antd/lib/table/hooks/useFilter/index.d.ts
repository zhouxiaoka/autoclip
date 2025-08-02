import type { AnyObject } from '../../../_util/type';
import type { ColumnsType, ColumnType, FilterKey, FilterValue, GetPopupContainer, Key, TableLocale, TransformColumns } from '../../interface';
import { flattenKeys } from './FilterDropdown';
export interface FilterState<RecordType = AnyObject> {
    column: ColumnType<RecordType>;
    key: Key;
    filteredKeys?: FilterKey;
    forceFiltered?: boolean;
}
export declare const getFilterData: <RecordType extends AnyObject = AnyObject>(data: RecordType[], filterStates: FilterState<RecordType>[], childrenColumnName: string) => RecordType[];
export interface FilterConfig<RecordType = AnyObject> {
    prefixCls: string;
    dropdownPrefixCls: string;
    mergedColumns: ColumnsType<RecordType>;
    locale: TableLocale;
    onFilterChange: (filters: Record<string, FilterValue | null>, filterStates: FilterState<RecordType>[]) => void;
    getPopupContainer?: GetPopupContainer;
    rootClassName?: string;
}
declare const useFilter: <RecordType extends AnyObject = AnyObject>(props: FilterConfig<RecordType>) => [TransformColumns<RecordType>, FilterState<RecordType>[], Record<string, FilterValue | null>];
export { flattenKeys };
export default useFilter;
