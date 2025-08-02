import * as React from 'react';
import type { DefaultOptionType, SingleValueType } from '../Cascader';
export declare const FIX_LABEL = "__cascader_fix_label__";
export interface ColumnProps<OptionType extends DefaultOptionType = DefaultOptionType> {
    prefixCls: string;
    multiple?: boolean;
    options: OptionType[];
    /** Current Column opened item key */
    activeValue?: React.Key;
    /** The value path before current column */
    prevValuePath: React.Key[];
    onToggleOpen: (open: boolean) => void;
    onSelect: (valuePath: SingleValueType, leaf: boolean) => void;
    onActive: (valuePath: SingleValueType) => void;
    checkedSet: Set<React.Key>;
    halfCheckedSet: Set<React.Key>;
    loadingKeys: React.Key[];
    isSelectable: (option: DefaultOptionType) => boolean;
    disabled?: boolean;
}
export default function Column<OptionType extends DefaultOptionType = DefaultOptionType>({ prefixCls, multiple, options, activeValue, prevValuePath, onToggleOpen, onSelect, onActive, checkedSet, halfCheckedSet, loadingKeys, isSelectable, disabled: propsDisabled, }: ColumnProps<OptionType>): React.JSX.Element;
