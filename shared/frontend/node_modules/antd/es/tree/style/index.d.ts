import type { CSSInterpolation, CSSObject } from '@ant-design/cssinjs';
import type { AliasToken, CSSUtil, FullToken, GetDefaultToken } from '../../theme/internal';
export interface TreeSharedToken {
    /**
     * @desc 节点标题高度
     * @descEN Node title height
     */
    titleHeight: number;
    /**
     * @desc 缩进宽度
     * @descEN Indent width of tree
     */
    indentSize?: number;
    /**
     * @desc 节点悬浮态背景色
     * @descEN Background color of hovered node
     */
    nodeHoverBg: string;
    /**
     * @desc 节点悬浮态态文字颜色
     * @descEN Text color of hovered node
     */
    nodeHoverColor: string;
    /**
     * @desc 节点选中态背景色
     * @descEN Background color of selected node
     */
    nodeSelectedBg: string;
    /**
     * @desc 节点选中态文字颜色
     * @descEN Text color of selected node
     */
    nodeSelectedColor: string;
}
export interface ComponentToken extends TreeSharedToken {
    /**
     * @desc 目录树节点选中文字颜色
     * @descEN Text color of selected directory node
     */
    directoryNodeSelectedColor: string;
    /**
     * @desc 目录树节点选中背景色
     * @descEN Background color of selected directory node
     */
    directoryNodeSelectedBg: string;
}
export type TreeToken = FullToken<'Tree'> & {
    treeCls: string;
    treeNodeCls: string;
    treeNodePadding: number | string;
};
export declare const genBaseStyle: (prefixCls: string, token: TreeToken) => CSSObject;
export declare const genTreeStyle: (prefixCls: string, token: AliasToken & TreeSharedToken & CSSUtil, 
/**
 * @descCN 是否启用目录树样式
 * @descEN Whether to enable directory style
 * @default true
 */
enableDirectory?: boolean) => CSSInterpolation;
export declare const initComponentToken: (token: AliasToken) => TreeSharedToken;
export declare const prepareComponentToken: GetDefaultToken<'Tree'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
