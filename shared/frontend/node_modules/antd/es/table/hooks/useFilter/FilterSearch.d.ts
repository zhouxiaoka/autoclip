import * as React from 'react';
import type { AnyObject } from '../../../_util/type';
import type { FilterSearchType, TableLocale } from '../../interface';
interface FilterSearchProps<RecordType = AnyObject> {
    value: string;
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    filterSearch: FilterSearchType<RecordType>;
    tablePrefixCls: string;
    locale: TableLocale;
}
declare const FilterSearch: <RecordType extends AnyObject = AnyObject>(props: FilterSearchProps<RecordType>) => React.JSX.Element | null;
export default FilterSearch;
