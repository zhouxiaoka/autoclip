import React from 'react';
export type SemanticName = 'label' | 'content';
export interface DescriptionsContextProps {
    /** @deprecated Please use `styles={{ label: {} }}` instead */
    labelStyle?: React.CSSProperties;
    /** @deprecated Please use `styles={{ content: {} }}` instead */
    contentStyle?: React.CSSProperties;
    styles?: Partial<Record<SemanticName, React.CSSProperties>>;
    classNames?: Partial<Record<SemanticName, string>>;
}
declare const DescriptionsContext: React.Context<DescriptionsContextProps>;
export default DescriptionsContext;
