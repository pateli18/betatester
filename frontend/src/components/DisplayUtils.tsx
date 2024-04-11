import { Badge, badgeVariants } from "@/components/ui/badge";
import { ModelChat, ScrapeStatus } from "../types";
import Markdown from "react-markdown";
import { ReloadIcon, StopIcon } from "@radix-ui/react-icons";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { getChatResponse, stopScrape } from "../utils/apiCalls";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";

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

export const ChatPanel = (props: {
  updateChat: (message: ModelChat[]) => void;
  chat: ModelChat[];
}) => {
  const [chatLoading, setChatLoading] = useState<boolean>(false);
  const [input, setInput] = useState<string>("");
  const cancelRef = useRef<boolean>(false);

  const cancelOperation = () => {
    cancelRef.current = true;
  };

  const handleKeyDown = (
    event: React.KeyboardEvent<HTMLTextAreaElement>
  ): void => {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing &&
      !chatLoading
    ) {
      event.preventDefault();
      if (input !== "") {
        userMessage(input);
      }
    }
  };

  const userMessage = (input: string) => {
    props.updateChat([...props.chat, { role: "user", content: input }]);
  };

  useEffect(() => {
    if (
      props.chat.length > 0 &&
      props.chat[props.chat.length - 1].role === "user" &&
      !chatLoading
    ) {
      onSubmit(props.chat);
    }
  }, [props.chat]);

  const onSubmit = async (chat: ModelChat[]) => {
    cancelRef.current = false;
    setChatLoading(true);
    setInput("");
    try {
      for await (const chatOutput of getChatResponse(chat)) {
        if (cancelRef.current) {
          break;
        }

        props.updateChat([...chat, chatOutput.content]);
      }
    } catch (e) {
      console.error("error getting explanation", e);
      toast.error("Something went wrong, try again");
    }
    setChatLoading(false);
  };

  return (
    <div>
      <div className="relative flex">
        <Textarea
          tabIndex={0}
          onKeyDown={handleKeyDown}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={"Enter your message here..."}
          spellCheck={false}
          className="pr-20"
          disabled={chatLoading}
        />
        <div className="absolute right-0 top-4 sm:right-4">
          {chatLoading ? (
            <Button size="sm" onClick={cancelOperation}>
              <StopIcon className="mr-2" />
              Stop
            </Button>
          ) : (
            <Button
              onClick={() => userMessage(input)}
              size="sm"
              disabled={input === "" || chatLoading}
            >
              Send
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};
