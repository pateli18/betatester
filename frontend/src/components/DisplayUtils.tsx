import { Badge, badgeVariants } from "@/components/ui/badge";
import { ScrapeStatus } from "../types";
import Markdown from "react-markdown";
import { ReloadIcon, StopIcon } from "@radix-ui/react-icons";
import { ReactNode, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { stopScrape } from "../utils/apiCalls";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

export const StatusDisplay = (props: { status: ScrapeStatus }) => {
  switch (props.status) {
    case "running":
      return (
        <Badge className="bg-blue-500">
          Running
          <ReloadIcon className="w-2 h-2 ml-1 animate-spin" />
        </Badge>
      );
    case "completed":
      return <Badge className="bg-green-500">Completed</Badge>;
    case "stopped":
      return <Badge className="bg-gray-500">Stopped</Badge>;
    case "failed":
      return <Badge className="bg-red-500">Failed</Badge>;
  }
};

export const CustomMarkdown = (props: { content: string }) => {
  return <Markdown className="prose" children={props.content} />;
};

export const CounterDisplay = (props: {
  count: number;
  total: number;
  text: string;
}) => {
  const pct = props.count / props.total;
  let badgeColor = "bg-green-500";
  if (pct > 0.8 && pct < 1) {
    badgeColor = "bg-yellow-500";
  } else if (pct >= 1) {
    badgeColor = "bg-red-500";
  }

  return (
    <Badge className={badgeColor}>
      {props.count}/{props.total} {props.text}
    </Badge>
  );
};

export const AutoScroll = (props: {
  children: ReactNode;
  disabled?: boolean;
}) => {
  const endOfContentRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    endOfContentRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (!props.disabled) {
      scrollToBottom();
    }
  }, [props.children]);

  return (
    <div className="overflow-y-auto h-[100%]">
      {props.children}
      <div ref={endOfContentRef} />
    </div>
  );
};

export const TraceLink = (props: { trace_url: string }) => {
  const handleClick = (
    event: React.MouseEvent<HTMLAnchorElement, MouseEvent>
  ) => {
    event.stopPropagation();
  };
  return (
    <a
      href={props.trace_url}
      target="_blank"
      className={badgeVariants({ variant: "secondary" })}
      onClick={handleClick}
    >
      View Playwright Trace
    </a>
  );
};

export const StopButton = (props: {
  configId: string;
  scrapeId: string;
  reload: boolean;
}) => {
  const [stopLoading, setStopLoading] = useState<boolean>(false);

  const onClickStop = async (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    setStopLoading(true);
    const response = await stopScrape(props.configId, props.scrapeId);
    if (response) {
      toast.success("Test stopped");
      if (props.reload) {
        window.location.reload();
      }
    } else {
      toast.error("Failed to stop test");
    }
    setStopLoading(false);
  };

  return (
    <Button variant="destructive" onClick={onClickStop}>
      {stopLoading ? (
        <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
      ) : (
        <StopIcon className="mr-2 h-4 w-4" />
      )}
      Stop
    </Button>
  );
};

export const ConfigInfo = (props: {
  name?: string;
  high_level_goal: string;
  url: string;
}) => {
  return (
    <div className="space-y-2">
      {props.name && <div className="text-lg font-bold">{props.name}</div>}
      <div className="text-muted-foreground">{props.high_level_goal}</div>
      <div>
        <a
          href={props.url}
          target="_blank"
          rel="noreferrer"
          className="hover:underline"
        >
          {props.url}
        </a>
      </div>
    </div>
  );
};

export const DataLoading = () => {
  return (
    <div className="flex items-center justify-center h-40">
      <Loader2 className="h-8 w-8 animate-spin" />
      <div className="ml-2">Loading Data</div>
    </div>
  );
};
