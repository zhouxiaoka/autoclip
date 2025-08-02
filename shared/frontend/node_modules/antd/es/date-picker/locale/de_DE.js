import CalendarLocale from "rc-picker/es/locale/de_DE";
import TimePickerLocale from '../../time-picker/locale/de_DE';
// Merge into a locale object
const locale = {
  lang: Object.assign({
    placeholder: 'Datum auswählen',
    rangePlaceholder: ['Startdatum', 'Enddatum'],
    shortWeekDays: ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'],
    shortMonths: ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']
  }, CalendarLocale),
  timePickerLocale: Object.assign({}, TimePickerLocale)
};
// All settings at:
// https://github.com/ant-design/ant-design/issues/424
export default locale;