import { useEffect, useState } from "react";
import { Config, ConfigMetadata, RunEventMetadata } from "../types";
import { Layout } from "../components/Layout";
import { getAllConfigs, getConfig, startScrape } from "../utils/apiCalls";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  ExclamationTriangleIcon,
  InfoCircledIcon,
  PlusIcon,
} from "@radix-ui/react-icons";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { TestEventHistoryView } from "../components/TestHistoryView";
import { TestConfigForm } from "../components/TestConfigForm";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { loadAndFormatDate } from "../utils/date";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { ConfigInfo, DataLoading } from "../components/DisplayUtils";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const ConfigDrawer = (props: {
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
  setConfigId: (configId: string) => void;
}) => {
  return (
    <Drawer open={props.drawerOpen} onOpenChange={props.setDrawerOpen}>
      <DrawerContent className="h-[90%]">
        <DrawerHeader>
          <DrawerTitle>Configure Test</DrawerTitle>
        </DrawerHeader>
        <div className="p-4 space-y-5 overflow-y-auto">
          <TestConfigForm
            config={null}
            successCallback={(configId) => {
              props.setConfigId(configId);
              props.setDrawerOpen(false);
            }}
          />
        </div>
      </DrawerContent>
    </Drawer>
  );
};

const ConfigSelection = (props: {
  configs: ConfigMetadata[];
  configId: string | null;
  setConfigId: (configId: string) => void;
}) => {
  return (
    <Select
      value={props.configId ?? undefined}
      onValueChange={props.setConfigId}
    >
      <SelectTrigger className="overflow-hidden whitespace-nowrap w-[250px]">
        <SelectValue placeholder="Select Service" />
      </SelectTrigger>
      <SelectContent>
        <div className="overflow-y-scroll h-[200px]">
          {props.configs.map((config) => (
            <SelectItem key={config.config_id} value={config.config_id}>
              <div className="space-x-2">
                <span>{config.name}</span>
                <span className="text-gray-400">
                  {loadAndFormatDate(config.last_updated)}
                </span>
              </div>
            </SelectItem>
          ))}
        </div>
      </SelectContent>
    </Select>
  );
};

const ConfigViewControls = (props: {
  configId: string | null;
  configMetadata: ConfigMetadata[];
  setConfigId: (configId: string | null) => void;
}) => {
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (props.configId === null && drawerOpen === false) {
      props.setConfigId(
        props.configMetadata.length > 0
          ? props.configMetadata[0].config_id
          : null
      );
    }
  }, [drawerOpen]);

  return (
    <>
      <ConfigDrawer
        drawerOpen={drawerOpen}
        setDrawerOpen={setDrawerOpen}
        setConfigId={props.setConfigId}
      />
      <div className="flex flex-wrap items-center space-x-2 py-1">
        <Button
          onClick={() => {
            props.setConfigId(null);
            setDrawerOpen(true);
          }}
          variant="secondary"
        >
          <PlusIcon className="w-4 h-4 mr-2" />
          New Test
        </Button>
        {props.configMetadata.length > 0 && (
          <ConfigSelection
            configs={props.configMetadata}
            configId={props.configId}
            setConfigId={props.setConfigId}
          />
        )}
      </div>
    </>
  );
};

export const HomeRoute = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [configId, setConfigId] = useState<string | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [configMetadata, setConfigMetadata] = useState<ConfigMetadata[]>([]);
  const [dataLoading, setDataLoading] = useState(false);
  const [runLoading, setRunLoading] = useState(false);
  const [testEvents, setTestEvents] = useState<RunEventMetadata[]>([]);
  const [useScrapeSpec, setUseScrapeSpec] = useState(true);

  useEffect(() => {
    getAllConfigs().then((data) => {
      if (data === null) {
        toast.error("Failed to fetch tests");
      } else {
        setConfigMetadata(data);
      }
    });
  }, []);

  useEffect(() => {
    if (configId !== null) {
      setDataLoading(true);
      getConfig(configId).then((data) => {
        if (data === null) {
          toast.error("Failed to fetch config");
          setConfig(null);
          setConfigId(null);
          setSearchParams({});
        } else {
          setTestEvents(data.history);
          setConfig(data.config);
        }
        setDataLoading(false);
      });
      if (configId !== searchParams.get("configId")) {
        setSearchParams({ configId });
      }
    }
  }, [configId]);

  useEffect(() => {
    if (configMetadata.length > 0 && configId === null) {
      setConfigId(configMetadata[0].config_id);
    }
  }, [configMetadata]);

  useEffect(() => {
    if (searchParams.has("configId")) {
      if (searchParams.get("configId") !== configId) {
        const newConfigId = searchParams.get("configId")!;
        setConfigId(newConfigId);
      }
    }
  }, [searchParams]);

  const handleRunClick = async () => {
    if (configId) {
      setRunLoading(true);
      const response = await startScrape(configId!, useScrapeSpec);
      if (response === null) {
        toast.error("Failed to start test");
      } else {
        navigate(`/scrape/${configId}/${response.scrape_id}`);
        toast.success("Test started");
      }
      setRunLoading(false);
    }
  };

  return (
    <Layout>
      <ConfigViewControls
        configId={configId}
        setConfigId={setConfigId}
        configMetadata={configMetadata}
      />
      {config !== null && (
        <ConfigInfo
          name={config.name}
          high_level_goal={config.high_level_goal}
          url={config.url}
        />
      )}
      {dataLoading ? (
        <DataLoading />
      ) : (
        <Tabs defaultValue="history">
          <div className="space-x-2 flex items-center">
            <TabsList>
              <TabsTrigger value="history">History</TabsTrigger>
              {config !== null && (
                <TabsTrigger value="config">Configure</TabsTrigger>
              )}
            </TabsList>
            {configId !== null && (
              <Button disabled={runLoading} onClick={handleRunClick}>
                Run
              </Button>
            )}
            <div className="flex items-center space-x-2">
              <Checkbox
                id="use-scrape-spec"
                checked={useScrapeSpec}
                onCheckedChange={(checked) => {
                  const value = typeof checked === "boolean" ? checked : true;
                  setUseScrapeSpec(value);
                }}
              />
              <label
                htmlFor="use-scrape-spec"
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                Use Generated Test Spec
              </label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <InfoCircledIcon className="h-4 w-4" />
                </TooltipTrigger>
                <TooltipContent className="w-[300px]">
                  <p>
                    A successful Ai test will automatically generate a
                    deterministic test that can be run without having to pay for
                    model inference on each test run. If the deterministic test
                    fails, the Ai test runs and fixes any issues. If you don't
                    want to run the deterministic test when one is available,
                    uncheck the box.
                  </p>
                </TooltipContent>
              </Tooltip>
            </div>
          </div>
          <TabsContent value="history">
            {testEvents.length > 0 ? (
              <TestEventHistoryView testEvents={testEvents} />
            ) : (
              <Alert>
                <ExclamationTriangleIcon className="h-4 w-4" />
                <AlertTitle>No History Available</AlertTitle>
                <AlertDescription>
                  Click {configId === null ? "New Test" : "Run"}
                </AlertDescription>
              </Alert>
            )}
          </TabsContent>
          {config !== null && (
            <TabsContent value="config">
              <TestConfigForm config={config} />
            </TabsContent>
          )}
        </Tabs>
      )}
    </Layout>
  );
};
