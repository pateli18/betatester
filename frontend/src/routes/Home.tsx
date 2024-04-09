import { RunStartForm } from "../components/RunStartForm";
import { Layout } from "../components/Layout";
import { useEffect, useState } from "react";
import { RunMessage } from "../types";
import { RunMessageView } from "../components/RunView";
import { toast } from "sonner";

export const HomeRoute = () => {
  const [runId, setRunId] = useState<string | null>(null);
  const [runMessage, setRunMessage] = useState<RunMessage | null>(null);

  let eventSource: EventSource | null;

  useEffect(() => {
    if (runId && runId) {
      eventSource = new EventSource(`/api/v1/scraper/status-ui/${runId}`);
      eventSource.onmessage = (event) => {
        const data: RunMessage = JSON.parse(event.data);
        setRunMessage(data);
        if (data.status !== "running") {
          switch (data.status) {
            case "completed":
              toast.success("Run completed");
              break;
            case "stopped":
              toast.info("Run stopped");
              break;
            case "failed":
              toast.error("Run failed");
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
  }, [runId]);
  return (
    <Layout>
      <RunStartForm setRunId={setRunId} />
      {runMessage && <RunMessageView runMessage={runMessage} />}
    </Layout>
  );
};
