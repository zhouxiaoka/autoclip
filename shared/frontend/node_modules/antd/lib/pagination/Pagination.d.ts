import * as React from 'react';
import type { PaginationLocale, PaginationProps as RcPaginationProps } from 'rc-pagination';
import type { SelectProps } from '../select';
export interface PaginationProps extends Omit<RcPaginationProps, 'showSizeChanger' | 'pageSizeOptions'> {
    showQuickJumper?: boolean | {
        goButton?: React.ReactNode;
    };
    size?: 'default' | 'small';
    responsive?: boolean;
    role?: string;
    totalBoundaryShowSizeChanger?: number;
    rootClassName?: string;
    showSizeChanger?: boolean | SelectProps;
    /** @deprecated Not official support. Will be removed in next major version. */
    selectComponentClass?: any;
    /** `string` type will be removed in next major version. */
    pageSizeOptions?: (string | number)[];
}
export type PaginationPosition = 'top' | 'bottom' | 'both';
export interface PaginationConfig extends Omit<PaginationProps, 'rootClassName'> {
    position?: PaginationPosition;
}
export type { PaginationLocale };
declare const Pagination: React.FC<PaginationProps>;
export default Pagination;
