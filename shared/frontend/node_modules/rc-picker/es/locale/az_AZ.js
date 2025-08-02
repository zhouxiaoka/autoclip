import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'az_AZ',
  today: 'Bugün',
  now: 'İndi',
  backToToday: 'Bugünə qayıt',
  ok: 'Təsdiq',
  clear: 'Təmizlə',
  week: 'Həftə',
  month: 'Ay',
  year: 'İl',
  timeSelect: 'vaxtı seç',
  dateSelect: 'tarixi seç',
  weekSelect: 'Həftə seç',
  monthSelect: 'Ay seç',
  yearSelect: 'il seç',
  decadeSelect: 'Onillik seçin',
  dateFormat: 'D.M.YYYY',
  dateTimeFormat: 'D.M.YYYY HH:mm:ss',
  previousMonth: 'Əvvəlki ay (PageUp)',
  nextMonth: 'Növbəti ay (PageDown)',
  previousYear: 'Sonuncu il (Control + left)',
  nextYear: 'Növbəti il (Control + right)',
  previousDecade: 'Sonuncu onillik',
  nextDecade: 'Növbəti onillik',
  previousCentury: 'Sonuncu əsr',
  nextCentury: 'Növbəti əsr'
});
export default locale;