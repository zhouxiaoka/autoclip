import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'ml_IN',
  today: 'ഇന്ന്',
  now: 'ഇപ്പോൾ',
  backToToday: 'ഇന്നത്തെ ദിവസത്തിലേക്ക് തിരിച്ചു പോകുക',
  ok: 'ശരിയാണ്',
  clear: 'നീക്കം ചെയ്യുക',
  week: 'ആഴ്ച',
  month: 'മാസം',
  year: 'വർഷം',
  timeSelect: 'സമയം തിരഞ്ഞെടുക്കുക',
  dateSelect: 'ദിവസം തിരഞ്ഞെടുക്കുക',
  weekSelect: 'വാരം തിരഞ്ഞെടുക്കുക',
  monthSelect: 'മാസം തിരഞ്ഞെടുക്കുക',
  yearSelect: 'വർഷം തിരഞ്ഞെടുക്കുക',
  decadeSelect: 'ദശാബ്ദം തിരഞ്ഞെടുക്കുക',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousMonth: 'കഴിഞ്ഞ മാസം (PageUp)',
  nextMonth: 'അടുത്ത മാസം (PageDown)',
  previousYear: 'കഴിഞ്ഞ വർഷം (Control + left)',
  nextYear: 'അടുത്ത വർഷം (Control + right)',
  previousDecade: 'കഴിഞ്ഞ ദശാബ്ദം',
  nextDecade: 'അടുത്ത ദശാബ്ദം',
  previousCentury: 'കഴിഞ്ഞ നൂറ്റാണ്ട്',
  nextCentury: 'അടുത്ത നൂറ്റാണ്ട്'
});
export default locale;