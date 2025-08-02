import * as React from 'react';
export interface TransferSearchProps {
    prefixCls?: string;
    placeholder?: string;
    onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
    handleClear?: () => void;
    value?: string;
    disabled?: boolean;
}
declare const Search: React.FC<TransferSearchProps>;
export default Search;
