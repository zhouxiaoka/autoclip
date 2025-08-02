import * as React from 'react';
import type { DataNode, ChangeEventExtra, SafeKey, FieldNames } from '../interface';
export declare function convertChildrenToData(nodes: React.ReactNode): DataNode[];
export declare function fillLegacyProps(dataNode: DataNode): DataNode;
export declare function fillAdditionalInfo(extra: ChangeEventExtra, triggerValue: SafeKey, checkedValues: SafeKey[], treeData: DataNode[], showPosition: boolean, fieldNames: FieldNames): void;
