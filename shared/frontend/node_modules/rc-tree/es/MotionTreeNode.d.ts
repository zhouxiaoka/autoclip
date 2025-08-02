import * as React from 'react';
import type { FlattenNode, TreeNodeProps } from './interface';
import { type TreeNodeRequiredProps } from './utils/treeUtil';
interface MotionTreeNodeProps extends Omit<TreeNodeProps, 'domRef'> {
    active: boolean;
    motion?: any;
    motionNodes?: FlattenNode[];
    onMotionStart: () => void;
    onMotionEnd: () => void;
    motionType?: 'show' | 'hide';
    treeNodeRequiredProps: TreeNodeRequiredProps;
}
declare const MotionTreeNode: React.ForwardRefExoticComponent<MotionTreeNodeProps & React.RefAttributes<HTMLDivElement>>;
export default MotionTreeNode;
