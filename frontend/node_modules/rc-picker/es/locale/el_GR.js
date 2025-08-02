import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'el_GR',
  today: 'Σήμερα',
  now: 'Τώρα',
  backToToday: 'Πίσω στη σημερινή μέρα',
  ok: 'OK',
  clear: 'Καθαρισμός',
  week: 'Εβδομάδα',
  month: 'Μήνας',
  year: 'Έτος',
  timeSelect: 'Επιλογή ώρας',
  dateSelect: 'Επιλογή ημερομηνίας',
  monthSelect: 'Επιλογή μήνα',
  yearSelect: 'Επιλογή έτους',
  decadeSelect: 'Επιλογή δεκαετίας',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'Προηγούμενος μήνας (PageUp)',
  nextMonth: 'Επόμενος μήνας (PageDown)',
  previousYear: 'Προηγούμενο έτος (Control + αριστερά)',
  nextYear: 'Επόμενο έτος (Control + δεξιά)',
  previousDecade: 'Προηγούμενη δεκαετία',
  nextDecade: 'Επόμενη δεκαετία',
  previousCentury: 'Προηγούμενος αιώνας',
  nextCentury: 'Επόμενος αιώνας'
});
export default locale;