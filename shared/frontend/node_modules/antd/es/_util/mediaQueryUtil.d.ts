type MQListenerHandler = (mql: MediaQueryList, handler: (e: MediaQueryListEvent) => void) => void;
export declare const addMediaQueryListener: MQListenerHandler;
export declare const removeMediaQueryListener: MQListenerHandler;
export {};
