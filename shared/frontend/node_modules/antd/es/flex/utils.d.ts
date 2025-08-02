import type { FlexProps } from './interface';
export declare const flexWrapValues: React.CSSProperties['flexWrap'][];
export declare const justifyContentValues: React.CSSProperties['justifyContent'][];
export declare const alignItemsValues: React.CSSProperties['alignItems'][];
declare function createFlexClassNames(prefixCls: string, props: FlexProps): string;
export default createFlexClassNames;
