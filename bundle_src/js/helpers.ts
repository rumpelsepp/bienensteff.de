import { Temporal } from "@js-temporal/polyfill";

function getParam(name: string): string | null {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get(name);
}

function getDateParam(): Temporal.PlainDate {
  const dateParam = getParam("date");

  if (dateParam === null) {
    return Temporal.Now.plainDateISO();
  }
  return Temporal.PlainDate.from(dateParam);
}

export { getParam, getDateParam };
