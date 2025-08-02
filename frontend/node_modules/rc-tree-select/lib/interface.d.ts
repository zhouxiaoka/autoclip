import type * as React from 'react';
import type { SafeKey, Key, DataNode as TreeDataNode } from 'rc-tree/lib/interface';
export type { SafeKey, Key };
export interface DataNode extends Record<string, any>, Omit<TreeDataNode, 'key' | 'children'> {
    key?: Key;
    value?: SafeKey;
    children?: DataNode[];
}
export type SelectSource = 'option' | 'selection' | 'input' | 'clear';
export interface LabeledValueType {
    key?: Key;
    value?: SafeKey;
    label?: React.ReactNode;
    /** Only works on `treeCheckStrictly` */
    halfChecked?: boolean;
}
export type DefaultValueType = SafeKey | LabeledValueType | (SafeKey | LabeledValueType)[];
export interface LegacyDataNode extends DataNode {
    props: any;
}
export interface FlattenDataNode {
    data: DataNode;
    key: Key;
    value: SafeKey;
    level: number;
    parent?: FlattenDataNode;
}
export interface SimpleModeConfig {
    id?: SafeKey;
    pId?: SafeKey;
    rootPId?: SafeKey;
}
/** @deprecated This is only used for legacy compatible. Not works on new code. */
export interface LegacyCheckedNode {
    pos: string;
    node: React.ReactElement;
    children?: LegacyCheckedNode[];
}
export interface ChangeEventExtra {
    /** @deprecated Please save prev value by control logic instead */
    preValue: LabeledValueType[];
    triggerValue: SafeKey;
    /** @deprecated Use `onSelect` or `onDeselect` instead. */
    selected?: boolean;
    /** @deprecated Use `onSelect` or `onDeselect` instead. */
    checked?: boolean;
    /** @deprecated This prop not work as react node anymore. */
    triggerNode: React.ReactElement;
    /** @deprecated This prop not work as react node anymore. */
    allCheckedNodes: LegacyCheckedNode[];
}
export interface FieldNames {
    value?: string;
    label?: string;
    children?: string;
    _title?: string[];
}
