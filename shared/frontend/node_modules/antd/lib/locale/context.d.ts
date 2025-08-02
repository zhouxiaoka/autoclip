import type { Locale } from '.';
export type LocaleContextProps = Locale & {
    exist?: boolean;
};
declare const LocaleContext: React.Context<LocaleContextProps | undefined>;
export default LocaleContext;
