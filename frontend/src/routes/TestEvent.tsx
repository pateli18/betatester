import { Layout } from "../components/Layout";
import { useEffect, useState } from "react";
import { RunMessage } from "../types";
import { RunMessageView } from "../components/RunView";
import { toast } from "sonner";
import { useParams } from "react-router-dom";
import { DataLoading } from "../components/DisplayUtils";

export const TestEventRoute = () => {
  const { configId, scrapeId } = useParams<{
    configId: string;
    scrapeId: string;
  }>();
  const [runMessage, setRunMessage] = useState<RunMessage | null>(null);

  let eventSource: EventSource | null;

  useEffect(() => {
    if (configId && scrapeId) {
      eventSource = new EventSource(
        `/api/v1/scraper/status-ui/${configId}/${scrapeId}`
      );
      eventSource.onmessage = (event) => {
        const data: RunMessage = JSON.parse(event.data);
        setRunMessage(data);
        if (data.status !== "running") {
          switch (data.status) {
            case "completed":
              toast.success("Test completed");
              break;
            case "stopped":
              toast.info("Test stopped");
              break;
            case "failed":
              toast.error("Test failed");
              break;
          }
          eventSource?.close();
        }
      };

      return () => {
        if (eventSource) {
          eventSource.close();
        }
      };
    } else {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
    }
  }, [configId, scrapeId]);
  return (
    <Layout>
      {runMessage ? (
        <RunMessageView runMessage={runMessage} />
      ) : (
        <DataLoading />
      )}
    </Layout>
  );
};
