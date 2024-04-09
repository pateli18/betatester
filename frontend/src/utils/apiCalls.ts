import { FileInfo } from "src/types";
import Ajax from "./Ajax";

export const startRun = async (
  url: string,
  highLevelGoal: string,
  maxPageViews: number,
  maxTotalActions: number,
  maxActionsPerStep: number,
  viewportWidth: number,
  viewportHeight: number,
  variables: { [key: string]: string },
  files: { [key: string]: FileInfo }
) => {
  let response = null;
  try {
    response = await Ajax.req<{ scrape_id: string }>({
      url: "/api/v1/scraper/run",
      method: "POST",
      body: {
        url: url,
        high_level_goal: highLevelGoal,
        max_page_views: maxPageViews,
        max_total_actions: maxTotalActions,
        max_action_attempts_per_step: maxActionsPerStep,
        viewport_width: viewportWidth,
        viewport_height: viewportHeight,
        variables: variables,
        files: files,
      },
    });
  } catch (e) {
    console.error(e);
  }
  return response;
};

export const stopRun = async (runId: string) => {
  let response = false;
  try {
    await Ajax.req({
      url: `/api/v1/scraper/stop/${runId}`,
      method: "POST",
      body: {},
    });
    response = true;
  } catch (e) {
    console.error(e);
  }
  return response;
};
