import { useEffect, useState } from "react";
import { Action, ModelChat, RunMessage, ScrapeStatus, RunStep } from "../types";
import {
  ChatPanel,
  ConfigInfo,
  CounterDisplay,
  CustomMarkdown,
  StatusDisplay,
  StopButton,
  TraceLink,
} from "./DisplayUtils";
import { Button } from "@/components/ui/button";
import { ChevronLeftIcon, ChevronRightIcon } from "@radix-ui/react-icons";
import { loadAndFormatDate } from "../utils/date";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { useNavigate } from "react-router-dom";

const DebugChatView = (props: { chat: ModelChat[]; title: string }) => {
  const [modelChat, setModelChat] = useState<ModelChat[]>(props.chat);

  useEffect(() => {
    setModelChat(props.chat);
  }, [props.chat]);

  return (
    <AccordionItem value={props.title}>
      <AccordionTrigger>{props.title}</AccordionTrigger>
      <AccordionContent>
        <div className="space-y-2">
          <div>
            {modelChat.map((chat, index) => (
              <div key={index}>
                <h5 className="text-gray-500 mb-2">
                  {chat.role.toUpperCase()}
                </h5>
                <CustomMarkdown
                  content={
                    typeof chat.content === "string"
                      ? chat.content
                      : "**Image**"
                  }
                />
                <Separator className="mt-5 mb-5" />
              </div>
            ))}
            <ChatPanel chat={modelChat} updateChat={setModelChat} />
          </div>
        </div>
      </AccordionContent>
    </AccordionItem>
  );
};

const DebugStepView = (props: {
  nextStepChat: ModelChat[] | null;
  chooseActionChat: ModelChat[] | null;
}) => {
  let chooseActionChatFmt = null;
  if (props.chooseActionChat) {
    chooseActionChatFmt = props.chooseActionChat.map((chat) => {
      if (chat.role === "assistant" && typeof chat.content === "string") {
        // attempt to load the content as JSON, prettify if successful and wrap in ```json\n...\n```
        try {
          let json = JSON.parse(chat.content);
          json = `\`\`\`json\n${json}\n\`\`\``;
          return { ...chat, content: json };
        } catch (e) {
          return chat;
        }
      } else {
        return chat;
      }
    });
  }

  return (
    <>
      <h3 className="text-lg font-medium">Debug</h3>
      <Accordion type="single" collapsible className="w-[660px]">
        {props.nextStepChat && (
          <DebugChatView chat={props.nextStepChat} title="Next Step Chat" />
        )}
        {chooseActionChatFmt && (
          <DebugChatView chat={chooseActionChatFmt} title="Action Chat" />
        )}
      </Accordion>
    </>
  );
};

const StepStatus = (props: { status: ScrapeStatus; timestamp: string }) => {
  let message: JSX.Element;
  let fmtTimestamp = loadAndFormatDate(props.timestamp);
  switch (props.status) {
    case "running":
      message = (
        <div className="text-xs text-blue-500">{`Last updated: ${fmtTimestamp}`}</div>
      );
      break;
    case "completed":
      message = (
        <div className="text-xs text-green-500">{`Completed: ${fmtTimestamp}`}</div>
      );
      break;
    case "failed":
      message = (
        <div className="text-xs text-red-500">{`Failed: ${fmtTimestamp}`}</div>
      );
      break;
    case "stopped":
      message = (
        <div className="text-xs text-gray-500">{`Stopped: ${fmtTimestamp}`}</div>
      );
      break;
  }

  return message;
};

const StepAction = (props: { action: Action }) => {
  return (
    <div>
      <h5 className="text-gray-500">Element</h5>
      <div className="space-x-2">
        {props.action.element.role && (
          <Badge>{props.action.element.role}</Badge>
        )}
        {props.action.element.name && (
          <Badge>{props.action.element.name}</Badge>
        )}
        {props.action.element.selector && (
          <Badge>{props.action.element.selector}</Badge>
        )}
      </div>
      <h5 className="text-gray-500">Action</h5>
      <Badge>{props.action.action_type}</Badge>
      {props.action.action_value && (
        <>
          <h5 className="text-gray-500">Value</h5>
          <Badge>{props.action.action_value}</Badge>
        </>
      )}
    </div>
  );
};

const StepView = (props: {
  runId: string;
  runStep: RunStep;
  runIndex: number;
  numRuns: number;
  setRunIndex: (runIndex: number) => void;
}) => {
  return (
    <div className="space-y-5">
      {props.numRuns && props.numRuns > 1 && (
        <>
          <div className="text-lg font-medium">{`Step ${props.runIndex + 1} / ${
            props.numRuns
          }`}</div>
          <StepStatus
            status={props.runStep.status}
            timestamp={props.runStep.timestamp}
          />
          <div className="space-x-2 flex items-center">
            <Button
              disabled={props.runIndex === 0}
              onClick={() => props.setRunIndex(props.runIndex - 1)}
              variant="outline"
              size="sm"
            >
              <ChevronLeftIcon className="h-4 w-4" />
            </Button>
            <Button
              disabled={props.runIndex === props.numRuns - 1}
              onClick={() => props.setRunIndex(props.runIndex + 1)}
              variant="outline"
              size="sm"
            >
              <ChevronRightIcon className="h-4 w-4" />
            </Button>
          </div>
        </>
      )}
      <div>
        <h3 className="text-lg font-medium">Next Step</h3>
        <CustomMarkdown content={props.runStep.next_step} />
      </div>
      {props.runStep.action_count !== null && (
        <Badge>{`${props.runStep.action_count} Action Attempts`}</Badge>
      )}
      {props.runStep.action_count !== null && props.runStep.action ? (
        <StepAction action={props.runStep.action} />
      ) : (
        <Badge variant="destructive">No action</Badge>
      )}
      <div className="hover:scale-250 transition-transform duration-50 origin-bottom-left">
        <img
          src={`/data/screenshot/${props.runId}/${props.runStep.step_id}.png`}
          className="rounded-md shadow-md w-[300px] h-auto"
        />
      </div>
      {(props.runStep.debug_choose_action_chat ||
        props.runStep.debug_next_step_chat) && (
        <DebugStepView
          nextStepChat={props.runStep.debug_next_step_chat}
          chooseActionChat={props.runStep.debug_choose_action_chat}
        />
      )}
    </div>
  );
};

export const RunMessageView = (props: { runMessage: RunMessage }) => {
  const navigator = useNavigate();
  const [stepIndex, setStepIndex] = useState<number>(0);

  useEffect(() => {
    setStepIndex(Math.max(props.runMessage.steps.length - 1, 0));
  }, [props.runMessage.id]);

  useEffect(() => {
    if (props.runMessage.status === "running") {
      setStepIndex(Math.max(props.runMessage.steps.length - 1, 0));
    }
  }, [props.runMessage.steps.length]);

  return (
    <div className="space-y-5">
      <Button
        variant="secondary"
        onClick={() => navigator(`/?configId=${props.runMessage.config_id}`)}
      >
        Back to History
      </Button>
      <ConfigInfo
        url={props.runMessage.url}
        high_level_goal={props.runMessage.high_level_goal}
      />
      <div className="flex items-center space-x-2">
        {props.runMessage.using_scrape_spec && (
          <Badge
            variant={
              props.runMessage.scrape_spec_failed ? "destructive" : "default"
            }
          >
            {props.runMessage.scrape_spec_failed
              ? "Spec failed, using Ai"
              : "Using Spec"}
          </Badge>
        )}
        <StatusDisplay status={props.runMessage.status} />
        {props.runMessage.status === "running" && (
          <StopButton
            configId={props.runMessage.config_id}
            scrapeId={props.runMessage.id}
            reload={false}
          />
        )}
        <div className="text-xs text-muted-foreground">
          {loadAndFormatDate(props.runMessage.timestamp)}
        </div>
        {props.runMessage.status !== "running" && (
          <TraceLink trace_url={props.runMessage.trace_url} />
        )}
      </div>
      {props.runMessage.fail_reason && (
        <div className="text-xs text-red-500">
          {props.runMessage.fail_reason}
        </div>
      )}
      <div className="space-x-2">
        <CounterDisplay
          count={props.runMessage.page_views}
          total={props.runMessage.max_page_views}
          text="Max Page Views"
        />
        <CounterDisplay
          count={props.runMessage.action_count}
          total={props.runMessage.max_total_actions}
          text="Max Actions"
        />
      </div>
      {props.runMessage.steps.length > 0 && (
        <StepView
          runId={props.runMessage.id}
          runStep={props.runMessage.steps[stepIndex]}
          runIndex={stepIndex}
          numRuns={props.runMessage.steps.length}
          setRunIndex={setStepIndex}
        />
      )}
    </div>
  );
};
