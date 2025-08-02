import type { BuildInPlacements } from '@rc-component/trigger/lib/interface';
import type { BaseSelectPropsWithoutPrivate, BaseSelectRef } from 'rc-select';
import type { Placement } from 'rc-select/lib/BaseSelect';
import * as React from 'react';
import Panel from './Panel';
import { SHOW_CHILD, SHOW_PARENT } from './utils/commonUtil';
export interface BaseOptionType {
    disabled?: boolean;
    disableCheckbox?: boolean;
    label?: React.ReactNode;
    value?: string | number | null;
    children?: DefaultOptionType[];
}
export type DefaultOptionType = BaseOptionType & Record<string, any>;
export interface ShowSearchType<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType> {
    filter?: (inputValue: string, options: OptionType[], fieldNames: FieldNames<OptionType, ValueField>) => boolean;
    render?: (inputValue: string, path: OptionType[], prefixCls: string, fieldNames: FieldNames<OptionType, ValueField>) => React.ReactNode;
    sort?: (a: OptionType[], b: OptionType[], inputValue: string, fieldNames: FieldNames<OptionType, ValueField>) => number;
    matchInputWidth?: boolean;
    limit?: number | false;
}
export type ShowCheckedStrategy = typeof SHOW_PARENT | typeof SHOW_CHILD;
interface BaseCascaderProps<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType> extends Omit<BaseSelectPropsWithoutPrivate, 'tokenSeparators' | 'labelInValue' | 'mode' | 'showSearch'> {
    id?: string;
    prefixCls?: string;
    fieldNames?: FieldNames<OptionType, ValueField>;
    optionRender?: (option: OptionType) => React.ReactNode;
    children?: React.ReactElement;
    changeOnSelect?: boolean;
    displayRender?: (label: string[], selectedOptions?: OptionType[]) => React.ReactNode;
    checkable?: boolean | React.ReactNode;
    showCheckedStrategy?: ShowCheckedStrategy;
    autoClearSearchValue?: boolean;
    showSearch?: boolean | ShowSearchType<OptionType>;
    searchValue?: string;
    onSearch?: (value: string) => void;
    expandTrigger?: 'hover' | 'click';
    options?: OptionType[];
    /** @private Internal usage. Do not use in your production. */
    dropdownPrefixCls?: string;
    loadData?: (selectOptions: OptionType[]) => void;
    /** @deprecated Use `open` instead */
    popupVisible?: boolean;
    /** @deprecated Use `dropdownClassName` instead */
    popupClassName?: string;
    dropdownClassName?: string;
    dropdownMenuColumnStyle?: React.CSSProperties;
    /** @deprecated Use `placement` instead */
    popupPlacement?: Placement;
    placement?: Placement;
    builtinPlacements?: BuildInPlacements;
    /** @deprecated Use `onOpenChange` instead */
    onPopupVisibleChange?: (open: boolean) => void;
    /** @deprecated Use `onOpenChange` instead */
    onDropdownVisibleChange?: (open: boolean) => void;
    onOpenChange?: (open: boolean) => void;
    expandIcon?: React.ReactNode;
    loadingIcon?: React.ReactNode;
}
export interface FieldNames<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType> {
    label?: keyof OptionType;
    value?: keyof OptionType | ValueField;
    children?: keyof OptionType;
}
export type ValueType<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType> = keyof OptionType extends ValueField ? unknown extends OptionType['value'] ? OptionType[ValueField] : OptionType['value'] : OptionType[ValueField];
export type GetValueType<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType, Multiple extends boolean | React.ReactNode = false> = false extends Multiple ? ValueType<Required<OptionType>, ValueField>[] : ValueType<Required<OptionType>, ValueField>[][];
export type GetOptionType<OptionType extends DefaultOptionType = DefaultOptionType, Multiple extends boolean | React.ReactNode = false> = false extends Multiple ? OptionType[] : OptionType[][];
export interface CascaderProps<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType, Multiple extends boolean | React.ReactNode = false> extends BaseCascaderProps<OptionType, ValueField> {
    checkable?: Multiple;
    value?: GetValueType<OptionType, ValueField, Multiple>;
    defaultValue?: GetValueType<OptionType, ValueField, Multiple>;
    onChange?: (value: GetValueType<OptionType, ValueField, Multiple>, selectOptions: GetOptionType<OptionType, Multiple>) => void;
}
export type SingleValueType = (string | number)[];
export type InternalValueType = SingleValueType | SingleValueType[];
export interface InternalFieldNames extends Required<FieldNames> {
    key: string;
}
export type InternalCascaderProps = Omit<CascaderProps, 'onChange' | 'value' | 'defaultValue'> & {
    value?: InternalValueType;
    defaultValue?: InternalValueType;
    onChange?: (value: InternalValueType, selectOptions: BaseOptionType[] | BaseOptionType[][]) => void;
};
export type CascaderRef = Omit<BaseSelectRef, 'scrollTo'>;
declare const Cascader: (<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType, Multiple extends React.ReactNode = false>(props: CascaderProps<OptionType, ValueField, Multiple> & {
    children?: React.ReactNode;
} & {
    ref?: React.Ref<CascaderRef> | undefined;
}) => React.ReactElement) & {
    displayName?: string | undefined;
    SHOW_PARENT: typeof SHOW_PARENT;
    SHOW_CHILD: typeof SHOW_CHILD;
    Panel: typeof Panel;
};
export default Cascader;
