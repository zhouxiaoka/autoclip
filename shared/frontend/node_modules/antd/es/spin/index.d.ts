import * as React from 'react';
declare const _SpinSizes: readonly ["small", "default", "large"];
export type SpinSize = (typeof _SpinSizes)[number];
export type SpinIndicator = React.ReactElement<HTMLElement>;
export interface SpinProps {
    /** Customize prefix class name */
    prefixCls?: string;
    /** Additional class name of Spin */
    className?: string;
    /** Additional root class name of Spin */
    rootClassName?: string;
    /** Whether Spin is spinning */
    spinning?: boolean;
    /** Style of Spin */
    style?: React.CSSProperties;
    /** Size of Spin, options: `small`, `default` and `large` */
    size?: SpinSize;
    /** Customize description content when Spin has children */
    tip?: React.ReactNode;
    /** Specifies a delay in milliseconds for loading state (prevent flush) */
    delay?: number;
    /** The className of wrapper when Spin has children */
    wrapperClassName?: string;
    /** React node of the spinning indicator */
    indicator?: SpinIndicator;
    /** Children of Spin */
    children?: React.ReactNode;
    /** Display a backdrop with the `Spin` component */
    fullscreen?: boolean;
    percent?: number | 'auto';
}
export type SpinType = React.FC<SpinProps> & {
    setDefaultIndicator: (indicator: React.ReactNode) => void;
};
declare const Spin: SpinType;
export default Spin;
