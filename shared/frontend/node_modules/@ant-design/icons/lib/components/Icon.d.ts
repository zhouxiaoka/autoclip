import * as React from 'react';
export interface IconBaseProps extends React.HTMLProps<HTMLSpanElement> {
    spin?: boolean;
    rotate?: number;
}
export interface CustomIconComponentProps {
    width: string | number;
    height: string | number;
    fill?: string;
    viewBox?: string;
    className?: string;
    style?: React.CSSProperties;
}
export interface IconComponentProps extends IconBaseProps {
    viewBox?: string;
    component?: React.ComponentType<CustomIconComponentProps | React.SVGProps<SVGSVGElement>> | React.ForwardRefExoticComponent<CustomIconComponentProps>;
    ariaLabel?: React.AriaAttributes['aria-label'];
}
declare const Icon: React.ForwardRefExoticComponent<Omit<IconComponentProps, 'ref'> & React.RefAttributes<HTMLSpanElement>>;
export default Icon;
