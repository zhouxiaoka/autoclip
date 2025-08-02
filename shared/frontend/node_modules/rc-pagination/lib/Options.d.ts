import React from 'react';
import type { PaginationLocale } from './interface';
export type SizeChangerRender = (info: {
    disabled: boolean;
    size: number;
    onSizeChange: (value: string | number) => void;
    'aria-label': string;
    className: string;
    options: {
        label: string;
        value: string | number;
    }[];
}) => React.ReactNode;
interface OptionsProps {
    disabled?: boolean;
    locale: PaginationLocale;
    rootPrefixCls: string;
    selectPrefixCls?: string;
    pageSize: number;
    pageSizeOptions?: number[];
    goButton?: boolean | string;
    changeSize?: (size: number) => void;
    quickGo?: (value: number) => void;
    buildOptionText?: (value: number | string) => string;
    showSizeChanger: boolean;
    sizeChangerRender?: SizeChangerRender;
}
declare const Options: React.FC<OptionsProps>;
export default Options;
