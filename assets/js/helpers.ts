import { DateTime } from "luxon";

function formatDate(date: DateTime): string {
  return date.setLocale('de-DE').toLocaleString({
    weekday: 'short',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  });
}

function getParam(name: string): string {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get(name);
}

function getDateParam(): DateTime {
  const dateParam = getParam("date");

  if (dateParam != null) {
    return DateTime.fromISO(dateParam).toLocal();
  }
  return DateTime.now().toLocal();
}

export { getParam, getDateParam };