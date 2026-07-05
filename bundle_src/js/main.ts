import { initAllCalendarWidgets } from "./calendars/render";
import { initAllCharts } from "./charts/render";

try {
    initAllCalendarWidgets();
} catch (error) {
    console.error("Failed to initialize calendar widgets:", error);
}

try {
    await initAllCharts();
} catch (error) {
    console.error("Failed to initialize charts:", error);
}
