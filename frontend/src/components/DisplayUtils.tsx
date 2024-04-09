import { Badge } from "@/components/ui/badge";
import { ScrapeStatus } from "../types";
import Markdown from "react-markdown";
import { ReloadIcon } from "@radix-ui/react-icons";
import { ReactNode, useEffect, useRef } from "react";

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
  if (pct > 0.6 && pct < 0.9) {
    badgeColor = "bg-yellow-500";
  } else if (pct >= 0.9) {
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
