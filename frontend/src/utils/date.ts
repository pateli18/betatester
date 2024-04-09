import { format } from "date-fns";

export const loadAndFormatDate = (rawDateString: string) => {
  // Parse the ISO format date
  let date = new Date(rawDateString);

  // convert date from utc to local
  date = new Date(date.getTime() - date.getTimezoneOffset() * 60 * 1000);

  // Format the date in a human-readable format
  const formattedDate = format(date, "PPpp");

  return formattedDate;
};
