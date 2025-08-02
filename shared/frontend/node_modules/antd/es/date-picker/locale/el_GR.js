import CalendarLocale from "rc-picker/es/locale/el_GR";
import TimePickerLocale from '../../time-picker/locale/el_GR';
// Merge into a locale object
const locale = {
  lang: Object.assign({
    placeholder: 'Επιλέξτε ημερομηνία',
    yearPlaceholder: 'Επιλέξτε έτος',
    quarterPlaceholder: 'Επιλέξτε τρίμηνο',
    monthPlaceholder: 'Επιλέξτε μήνα',
    weekPlaceholder: 'Επιλέξτε εβδομάδα',
    rangePlaceholder: ['Αρχική ημερομηνία', 'Τελική ημερομηνία'],
    rangeYearPlaceholder: ['Αρχικό έτος', 'Τελικό έτος'],
    rangeMonthPlaceholder: ['Αρχικός μήνας', 'Τελικός μήνας'],
    rangeQuarterPlaceholder: ['Αρχικό τρίμηνο', 'Τελικό τρίμηνο'],
    rangeWeekPlaceholder: ['Αρχική εβδομάδα', 'Τελική εβδομάδα']
  }, CalendarLocale),
  timePickerLocale: Object.assign({}, TimePickerLocale)
};
// All settings at:
// https://github.com/ant-design/ant-design/issues/424
export default locale;