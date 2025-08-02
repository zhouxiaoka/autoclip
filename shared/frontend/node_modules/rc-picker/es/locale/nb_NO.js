import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'nb_NO',
  today: 'I dag',
  now: 'Nå',
  backToToday: 'Gå til i dag',
  ok: 'OK',
  clear: 'Annuller',
  week: 'Uke',
  month: 'Måned',
  year: 'År',
  timeSelect: 'Velg tidspunkt',
  dateSelect: 'Velg dato',
  weekSelect: 'Velg uke',
  monthSelect: 'Velg måned',
  yearSelect: 'Velg år',
  decadeSelect: 'Velg tiår',
  dateFormat: 'DD.MM.YYYY',
  dayFormat: 'DD',
  dateTimeFormat: 'DD.MM.YYYY HH:mm:ss',
  previousMonth: 'Forrige måned (PageUp)',
  nextMonth: 'Neste måned (PageDown)',
  previousYear: 'Forrige år (Control + venstre)',
  nextYear: 'Neste år (Control + høyre)',
  previousDecade: 'Forrige tiår',
  nextDecade: 'Neste tiår',
  previousCentury: 'Forrige århundre',
  nextCentury: 'Neste århundre'
});
export default locale;