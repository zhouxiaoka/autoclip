import * as React from 'react';
import type { CascaderProps, DefaultOptionType } from './Cascader';
export type PickType = 'value' | 'defaultValue' | 'changeOnSelect' | 'onChange' | 'options' | 'prefixCls' | 'checkable' | 'fieldNames' | 'showCheckedStrategy' | 'loadData' | 'expandTrigger' | 'expandIcon' | 'loadingIcon' | 'className' | 'style' | 'direction' | 'notFoundContent' | 'disabled';
export type PanelProps<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType, Multiple extends boolean | React.ReactNode = false> = Pick<CascaderProps<OptionType, ValueField, Multiple>, PickType>;
export default function Panel<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType, Multiple extends boolean | React.ReactNode = false>(props: PanelProps<OptionType, ValueField, Multiple>): React.JSX.Element;
