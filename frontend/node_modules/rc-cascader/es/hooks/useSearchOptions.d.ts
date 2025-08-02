import type { DefaultOptionType, InternalFieldNames, ShowSearchType } from '../Cascader';
export declare const SEARCH_MARK = "__rc_cascader_search_mark__";
declare const useSearchOptions: (search: string, options: DefaultOptionType[], fieldNames: InternalFieldNames, prefixCls: string, config: ShowSearchType, enableHalfPath?: boolean) => DefaultOptionType[];
export default useSearchOptions;
