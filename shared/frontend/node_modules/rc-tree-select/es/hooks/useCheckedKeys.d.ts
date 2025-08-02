import * as React from 'react';
import type { DataEntity } from 'rc-tree/lib/interface';
import type { LabeledValueType, SafeKey } from '../interface';
declare const useCheckedKeys: (rawLabeledValues: LabeledValueType[], rawHalfCheckedValues: LabeledValueType[], treeConduction: boolean, keyEntities: Record<SafeKey, DataEntity>) => React.Key[][];
export default useCheckedKeys;
