/// <reference types="react" />
export interface IconContextProps {
    prefixCls?: string;
    rootClassName?: string;
    csp?: {
        nonce?: string;
    };
    layer?: string;
}
declare const IconContext: import("react").Context<IconContextProps>;
export default IconContext;
