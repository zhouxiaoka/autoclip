import * as React from 'react';
import Slider from "../components/Slider";
export default function useComponent(components) {
  return React.useMemo(function () {
    var _ref = components || {},
      slider = _ref.slider;
    return [slider || Slider];
  }, [components]);
}