import { Separator } from "@/components/ui/separator";
import { useNavigate } from "react-router-dom";
import { RunEventMetadata } from "src/types";
import { loadAndFormatDate } from "../utils/date";
import { StatusDisplay, StopButton, TraceLink } from "./DisplayUtils";

const IdDisplay = (props: { id: string }) => {
  const id = props.id.substring(0, 5);

  return <span className="font-bold">{id}</span>;
};

const TestEventMetadataView = (props: { event: RunEventMetadata }) => {
  const navigate = useNavigate();
  return (
    <div
      className="space-x-5 hover:bg-gray-100 py-3 rounded-lg hover:cursor-pointer"
      onClick={() =>
        navigate(`/scrape/${props.event.config_id}/${props.event.id}`)
      }
    >
      <StatusDisplay status={props.event.status} />
      <IdDisplay id={props.event.id} />
      <span className="text-muted-foreground text-xs">
        {loadAndFormatDate(props.event.timestamp)}
      </span>
      {props.event.status === "running" && (
        <StopButton
          configId={props.event.config_id}
          scrapeId={props.event.id}
          reload={true}
        />
      )}
      {props.event.status !== "running" && (
        <TraceLink trace_url={props.event.trace_url} />
      )}
    </div>
  );
};

export const TestEventHistoryView = (props: {
  testEvents: RunEventMetadata[];
}) => {
  return (
    <div>
      {props.testEvents.map((event, i) => (
        <div key={event.id}>
          <TestEventMetadataView event={event} />
          {i !== props.testEvents.length - 1 && <Separator />}
        </div>
      ))}
    </div>
  );
};
