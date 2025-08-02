import * as React from 'react';
export interface TransferLocale {
    description: string;
}
export type SemanticName = 'root' | 'image' | 'description' | 'footer';
export interface EmptyProps {
    prefixCls?: string;
    className?: string;
    rootClassName?: string;
    style?: React.CSSProperties;
    /** @deprecated Please use `styles={{ image: {} }}` instead */
    imageStyle?: React.CSSProperties;
    image?: React.ReactNode;
    description?: React.ReactNode;
    children?: React.ReactNode;
    classNames?: Partial<Record<SemanticName, string>>;
    styles?: Partial<Record<SemanticName, React.CSSProperties>>;
}
type CompoundedComponent = React.FC<EmptyProps> & {
    PRESENTED_IMAGE_DEFAULT: React.ReactNode;
    PRESENTED_IMAGE_SIMPLE: React.ReactNode;
};
declare const Empty: CompoundedComponent;
export default Empty;
