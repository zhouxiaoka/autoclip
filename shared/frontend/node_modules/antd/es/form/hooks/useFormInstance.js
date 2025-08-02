import * as React from 'react';
import { FormContext } from '../context';
export default function useFormInstance() {
  const {
    form
  } = React.useContext(FormContext);
  return form;
}