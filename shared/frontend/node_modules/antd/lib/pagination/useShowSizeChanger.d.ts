import type { PaginationProps } from '.';
import type { SelectProps } from '../select';
export default function useShowSizeChanger(showSizeChanger?: PaginationProps['showSizeChanger']): [show: boolean | undefined, selectProps: SelectProps<any, import("rc-select/lib/Select").DefaultOptionType> | undefined];
