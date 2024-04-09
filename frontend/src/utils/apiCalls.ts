import { Config, ConfigMetadata, FileInfo, RunEventMetadata } from "src/types";
import Ajax from "./Ajax";

export const upsertConfig = async (
  configId: string | null,
  name: string,
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
    response = await Ajax.req<{ config_id: string }>({
      url: "/api/v1/config/upsert",
      method: "POST",
      body: {
        config_id: configId,
        url: url,
        name: name,
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

export const startScrape = async (configId: string) => {
  let response = null;
  try {
    response = await Ajax.req<{ scrape_id: string }>({
      url: `/api/v1/scraper/start/${configId}`,
      method: "POST",
      body: {},
    });
  } catch (e) {
    console.error(e);
  }
  return response;
};

export const stopScrape = async (configId: string, scrapeId: string) => {
  let response = false;
  try {
    await Ajax.req({
      url: `/api/v1/scraper/stop/${configId}/${scrapeId}`,
      method: "POST",
      body: {},
    });
    response = true;
  } catch (e) {
    console.error(e);
  }
  return response;
};

export const getAllConfigs = async () => {
  let response = null;
  try {
    response = await Ajax.req<ConfigMetadata[]>({
      url: `/api/v1/config/all`,
      method: "GET",
    });
  } catch (e) {
    console.error(e);
  }
  return response;
};

export const getConfig = async (configId: string) => {
  let response = null;
  try {
    response = await Ajax.req<{
      config: Config;
      history: RunEventMetadata[];
    }>({
      url: `/api/v1/config/${configId}`,
      method: "GET",
    });
  } catch (e) {
    console.error(e);
  }
  return response;
};
