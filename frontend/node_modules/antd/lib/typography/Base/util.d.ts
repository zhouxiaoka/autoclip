export declare function toList<T>(val: T | T[]): T[];
export declare function getNode(dom: React.ReactNode, defaultNode: React.ReactNode, needDom?: boolean): React.ReactNode;
/**
 * Check for element is native ellipsis
 * ref:
 * - https://github.com/ant-design/ant-design/issues/50143
 * - https://github.com/ant-design/ant-design/issues/50414
 */
export declare function isEleEllipsis(ele: HTMLElement): boolean;
export declare const isValidText: (val: any) => val is string | number;
