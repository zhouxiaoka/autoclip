import * as React from 'react';
declare const DisabledContext: React.Context<boolean>;
export interface DisabledContextProps {
    disabled?: boolean;
    children?: React.ReactNode;
}
export declare const DisabledContextProvider: React.FC<DisabledContextProps>;
export default DisabledContext;
