"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = usePercent;
var React = _interopRequireWildcard(require("react"));
const AUTO_INTERVAL = 200;
const STEP_BUCKETS = [[30, 0.05], [70, 0.03], [96, 0.01]];
function usePercent(spinning, percent) {
  const [mockPercent, setMockPercent] = React.useState(0);
  const mockIntervalRef = React.useRef(null);
  const isAuto = percent === 'auto';
  React.useEffect(() => {
    if (isAuto && spinning) {
      setMockPercent(0);
      mockIntervalRef.current = setInterval(() => {
        setMockPercent(prev => {
          const restPTG = 100 - prev;
          for (let i = 0; i < STEP_BUCKETS.length; i += 1) {
            const [limit, stepPtg] = STEP_BUCKETS[i];
            if (prev <= limit) {
              return prev + restPTG * stepPtg;
            }
          }
          return prev;
        });
      }, AUTO_INTERVAL);
    }
    return () => {
      clearInterval(mockIntervalRef.current);
    };
  }, [isAuto, spinning]);
  return isAuto ? mockPercent : percent;
}