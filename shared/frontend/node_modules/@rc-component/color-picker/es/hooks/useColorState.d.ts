import type { Color } from '../color';
import type { ColorGenInput } from '../interface';
type ColorValue = ColorGenInput | undefined;
declare const useColorState: (defaultValue: ColorValue, value?: ColorValue) => [Color, React.Dispatch<React.SetStateAction<Color>>];
export default useColorState;
