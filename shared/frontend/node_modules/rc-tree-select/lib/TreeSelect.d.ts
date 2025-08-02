import type { BaseSelectPropsWithoutPrivate, BaseSelectRef } from 'rc-select';
import type { IconType } from 'rc-tree/lib/interface';
import type { ExpandAction } from 'rc-tree/lib/Tree';
import * as React from 'react';
import TreeNode from './TreeNode';
import type { CheckedStrategy } from './utils/strategyUtil';
import { SHOW_ALL, SHOW_CHILD, SHOW_PARENT } from './utils/strategyUtil';
import type { SafeKey, DataNode, SimpleModeConfig, ChangeEventExtra, FieldNames, LegacyDataNode } from './interface';
export interface TreeSelectProps<ValueType = any, OptionType extends DataNode = DataNode> extends Omit<BaseSelectPropsWithoutPrivate, 'mode'> {
    prefixCls?: string;
    id?: string;
    children?: React.ReactNode;
    value?: ValueType;
    defaultValue?: ValueType;
    onChange?: (value: ValueType, labelList: React.ReactNode[], extra: ChangeEventExtra) => void;
    searchValue?: string;
    /** @deprecated Use `searchValue` instead */
    inputValue?: string;
    onSearch?: (value: string) => void;
    autoClearSearchValue?: boolean;
    filterTreeNode?: boolean | ((inputValue: string, treeNode: DataNode) => boolean);
    treeNodeFilterProp?: string;
    onSelect?: (value: ValueType, option: OptionType) => void;
    onDeselect?: (value: ValueType, option: OptionType) => void;
    showCheckedStrategy?: CheckedStrategy;
    treeNodeLabelProp?: string;
    fieldNames?: FieldNames;
    multiple?: boolean;
    treeCheckable?: boolean | React.ReactNode;
    treeCheckStrictly?: boolean;
    labelInValue?: boolean;
    maxCount?: number;
    treeData?: OptionType[];
    treeDataSimpleMode?: boolean | SimpleModeConfig;
    loadData?: (dataNode: LegacyDataNode) => Promise<unknown>;
    treeLoadedKeys?: SafeKey[];
    onTreeLoad?: (loadedKeys: SafeKey[]) => void;
    treeDefaultExpandAll?: boolean;
    treeExpandedKeys?: SafeKey[];
    treeDefaultExpandedKeys?: SafeKey[];
    onTreeExpand?: (expandedKeys: SafeKey[]) => void;
    treeExpandAction?: ExpandAction;
    virtual?: boolean;
    listHeight?: number;
    listItemHeight?: number;
    listItemScrollOffset?: number;
    onDropdownVisibleChange?: (open: boolean) => void;
    treeTitleRender?: (node: OptionType) => React.ReactNode;
    treeLine?: boolean;
    treeIcon?: IconType;
    showTreeIcon?: boolean;
    switcherIcon?: IconType;
    treeMotion?: any;
}
declare const GenericTreeSelect: (<ValueType = any, OptionType extends DataNode = DataNode>(props: TreeSelectProps<ValueType, OptionType> & {
    children?: React.ReactNode;
} & {
    ref?: React.Ref<BaseSelectRef>;
}) => React.ReactElement) & {
    TreeNode: typeof TreeNode;
    SHOW_ALL: typeof SHOW_ALL;
    SHOW_PARENT: typeof SHOW_PARENT;
    SHOW_CHILD: typeof SHOW_CHILD;
};
export default GenericTreeSelect;
