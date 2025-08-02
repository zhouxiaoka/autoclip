export type UsePrefix = () => {
    /**
     * All the component use `@ant-design/cssinjs-utils` should have same `rootPrefixCls`.
     */
    rootPrefixCls: string;
    /**
     * `iconPrefixCls` comes from the setting of `@ant-design/icons`.
     * Here maybe little coupling but everyone need use this.
     */
    iconPrefixCls: string;
};
