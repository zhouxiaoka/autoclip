import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'hi_IN',
  today: 'आज',
  now: 'अभी',
  backToToday: 'आज तक',
  ok: 'ठीक',
  clear: 'स्पष्ट',
  week: 'सप्ताह',
  month: 'महीना',
  year: 'साल',
  timeSelect: 'समय का चयन करें',
  dateSelect: 'तारीख़ चुनें',
  weekSelect: 'एक सप्ताह चुनें',
  monthSelect: 'एक महीना चुनें',
  yearSelect: 'एक वर्ष चुनें',
  decadeSelect: 'एक दशक चुनें',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousMonth: 'पिछला महीना (पेजअप)',
  nextMonth: 'अगले महीने (पेजडाउन)',
  previousYear: 'पिछले साल (Ctrl + बाएं)',
  nextYear: 'अगले साल (Ctrl + दाहिना)',
  previousDecade: 'पिछला दशक',
  nextDecade: 'अगले दशक',
  previousCentury: 'पीछ्ली शताब्दी',
  nextCentury: 'अगली सदी'
});
export default locale;