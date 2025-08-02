import type { ComponentToken, InputNumberToken } from './token';
export type { ComponentToken };
export declare const genRadiusStyle: ({ componentCls, borderRadiusSM, borderRadiusLG }: InputNumberToken, size: "lg" | "sm") => {
    [x: string]: {
        [x: string]: {
            borderStartEndRadius: number;
            borderEndEndRadius: number;
        } | {
            borderStartEndRadius: number;
            borderEndEndRadius?: undefined;
        } | {
            borderEndEndRadius: number;
            borderStartEndRadius?: undefined;
        };
    };
};
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
