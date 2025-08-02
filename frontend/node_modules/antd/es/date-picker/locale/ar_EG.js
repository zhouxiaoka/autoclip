import CalendarLocale from "rc-picker/es/locale/ar_EG";
import TimePickerLocale from '../../time-picker/locale/ar_EG';
// Merge into a locale object
const locale = {
  lang: Object.assign({
    placeholder: 'اختيار التاريخ',
    rangePlaceholder: ['البداية', 'النهاية'],
    yearFormat: 'YYYY',
    monthFormat: 'MMMM',
    monthBeforeYear: true,
    shortWeekDays: ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'],
    shortMonths: ['يناير', 'فبراير', 'مارس', 'إبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
  }, CalendarLocale),
  timePickerLocale: Object.assign({}, TimePickerLocale)
};
// All settings at:
// https://github.com/ant-design/ant-design/blob/master/components/date-picker/locale/example.json
export default locale;