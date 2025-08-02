import * as React from 'react';
import type { PickType } from 'rc-cascader/lib/Panel';
import type { CascaderProps, DefaultOptionType } from '.';
export type PanelPickType = Exclude<PickType, 'checkable'> | 'multiple' | 'rootClassName';
export type CascaderPanelProps<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType, Multiple extends boolean = boolean> = Pick<CascaderProps<OptionType, ValueField, Multiple>, PanelPickType>;
export type CascaderPanelAutoProps<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType> = (CascaderPanelProps<OptionType, ValueField> & {
    multiple?: false;
}) | (CascaderPanelProps<OptionType, ValueField, true> & {
    multiple: true;
});
declare function CascaderPanel<OptionType extends DefaultOptionType = DefaultOptionType, ValueField extends keyof OptionType = keyof OptionType>(props: CascaderPanelAutoProps<OptionType, ValueField>): React.ReactElement<unknown, string | React.JSXElementConstructor<any>>;
export default CascaderPanel;
