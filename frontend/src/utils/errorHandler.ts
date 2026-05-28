export const errorHandler = {
  handleError(error: unknown, context = 'App') {
    console.error(`[${context}]`, error)
  }
}
