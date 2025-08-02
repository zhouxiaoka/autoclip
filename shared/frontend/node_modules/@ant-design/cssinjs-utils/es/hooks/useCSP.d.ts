export type UseCSP = () => {
    nonce?: string;
};
/**
 * Provide a default hook since not everyone needs to config this.
 */
declare const useDefaultCSP: UseCSP;
export default useDefaultCSP;
