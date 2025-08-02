import type { Variant, ConfigProviderProps } from '../../config-provider';
type VariantComponents = keyof Pick<ConfigProviderProps, 'input' | 'inputNumber' | 'textArea' | 'mentions' | 'select' | 'cascader' | 'treeSelect' | 'datePicker' | 'timePicker' | 'rangePicker' | 'card'>;
/**
 * Compatible for legacy `bordered` prop.
 */
declare const useVariant: (component: VariantComponents, variant: Variant | undefined, legacyBordered?: boolean | undefined) => [Variant, boolean];
export default useVariant;
