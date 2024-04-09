import { useFieldArray, useForm } from "react-hook-form";
import * as z from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { startRun } from "../utils/apiCalls";
import { toast } from "sonner";
import { CaretSortIcon, ReloadIcon, TrashIcon } from "@radix-ui/react-icons";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { FileInfo } from "src/types";

const fileToFileInfo = async (file: File) => {
  return new Promise<FileInfo>((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = function () {
      if (typeof reader.result === "string") {
        resolve({
          name: file.name,
          b64_content: reader.result,
          mimeType: file.type,
        });
      } else {
        reject("Failed to read file");
      }
    };
    reader.onerror = function (error) {
      reject(error);
    };
    reader.readAsDataURL(file);
  });
};

const formSchema = z.object({
  url: z.string(),
  highLevelGoal: z.string(),
  maxPageViews: z.coerce.number(),
  maxTotalActions: z.coerce.number(),
  maxActionsPerStep: z.coerce.number(),
  viewportWidth: z.coerce.number(),
  viewportHeight: z.coerce.number(),
  files: z
    .array(
      z.object({
        key: z.string(),
        file: z
          .object({
            name: z.string(),
            b64_content: z.string(),
            mimeType: z.string(),
          })
          .nullable(),
      })
    )
    .optional(),
  keyValuePairs: z
    .array(z.object({ key: z.string(), value: z.string() }))
    .optional(),
});

const FormGroup = (props: { title: string; children: React.ReactNode }) => {
  return (
    <Collapsible>
      <CollapsibleTrigger asChild>
        <Button variant="ghost" className="pl-0">
          {props.title}
          <CaretSortIcon className="h-4 w-4" />
          <span className="sr-only">Toggle</span>
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>{props.children}</CollapsibleContent>
    </Collapsible>
  );
};

export const RunStartForm = (props: { setRunId: (runId: string) => void }) => {
  const [submitLoading, setSubmitLoading] = useState(false);
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      maxPageViews: 10,
      maxTotalActions: 20,
      maxActionsPerStep: 5,
      viewportHeight: 720,
      viewportWidth: 1280,
    },
  });

  const {
    fields: filesFields,
    append: appendFile,
    remove: removeFile,
  } = useFieldArray({
    name: "files",
    control: form.control,
  });

  const {
    fields: keyValuePairsFields,
    append: appendKeyValuePair,
    remove: removeKeyValuePair,
  } = useFieldArray({
    name: "keyValuePairs",
    control: form.control,
  });

  const onSubmit = async (data: z.infer<typeof formSchema>) => {
    setSubmitLoading(true);
    const response = await startRun(
      data.url,
      data.highLevelGoal,
      data.maxPageViews,
      data.maxTotalActions,
      data.maxActionsPerStep,
      data.viewportWidth,
      data.viewportHeight,
      data.keyValuePairs
        ? Object.fromEntries(
            data.keyValuePairs.map((pair) => [pair.key, pair.value])
          )
        : {},
      data.files
        ? Object.fromEntries(
            data.files
              .filter((file) => file.file !== null)
              .map((file) => [file.key, file.file!])
          )
        : {}
    );
    setSubmitLoading(false);
    if (response === null) {
      toast.error("Failed to start run");
    } else {
      props.setRunId(response.scrape_id);
      toast.success("Run started");
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
        <FormField
          control={form.control}
          name="url"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Url</FormLabel>
              <FormControl>
                <Input type="text" {...field} />
              </FormControl>
              <FormDescription>The url of the site to test</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="highLevelGoal"
          render={({ field }) => (
            <FormItem>
              <FormLabel>High Level Goal</FormLabel>
              <FormControl>
                <Input type="text" {...field} />
              </FormControl>
              <FormDescription>
                The high level goal you want the bot to accomplish (e.g. create
                a service)
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormGroup title="Variables">
          <div className="space-y-2">
            {keyValuePairsFields.map((field, index) => (
              <div key={field.id} className="flex items-center space-x-4">
                <FormField
                  key={`key-${field.id}`}
                  control={form.control}
                  name={`keyValuePairs.${index}.key`}
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <Input
                          type="text"
                          {...field}
                          placeholder="Key"
                          className="w-[200px]"
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  key={`value-${field.id}`}
                  control={form.control}
                  name={`keyValuePairs.${index}.value`}
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <Input
                          type="text"
                          {...field}
                          placeholder="Value"
                          className="w-[200px]"
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button
                  variant="destructive"
                  size="icon"
                  onClick={() => removeKeyValuePair(index)}
                >
                  <TrashIcon className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <Button
              variant="secondary"
              size="sm"
              className="mt-2"
              onClick={(e: any) => {
                e.preventDefault();
                appendKeyValuePair({ key: "", value: "" });
              }}
            >
              Add Variable
            </Button>
          </div>
        </FormGroup>
        <FormGroup title="Files">
          <div className="space-y-2">
            {filesFields.map((field, index) => (
              <div key={field.id} className="flex items-center space-x-4">
                <FormField
                  key={`key-${field.id}`}
                  control={form.control}
                  name={`files.${index}.key`}
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <Input
                          type="text"
                          {...field}
                          placeholder="Key"
                          className="w-[200px]"
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  key={`value-${field.id}`}
                  control={form.control}
                  name={`files.${index}.file`}
                  render={({ field }) => (
                    <FormItem>
                      <Input
                        type="file"
                        className="w-[200px]"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) {
                            fileToFileInfo(file)
                              .then((fileInfo) => {
                                form.setValue(`files.${index}.file`, fileInfo);
                                form.clearErrors(`files.${index}.file`);
                              })
                              .catch((e) => {
                                console.error(e);
                                form.setError(`files.${index}.file`, {
                                  type: "manual",
                                  message: "Failed to read file",
                                });
                              });
                          }
                        }}
                      />
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button
                  variant="destructive"
                  size="icon"
                  onClick={() => removeFile(index)}
                >
                  <TrashIcon className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <Button
              variant="secondary"
              size="sm"
              className="mt-2"
              onClick={(e) => {
                e.preventDefault();
                appendFile({ key: "", file: null });
              }}
            >
              Add File
            </Button>
          </div>
        </FormGroup>
        <FormGroup title="Limits">
          <>
            <FormField
              control={form.control}
              name="maxPageViews"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Max Page Views</FormLabel>
                  <FormControl>
                    <Input type="number" {...field} />
                  </FormControl>
                  <FormDescription>
                    The maximum number of pages to visit during the test, this
                    includes waiting for a page to load
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="maxTotalActions"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Max Total Actions</FormLabel>
                  <FormControl>
                    <Input type="number" {...field} />
                  </FormControl>
                  <FormDescription>
                    The maximum number of actions to take during the entire
                    test, multiple actions can occur on a single page
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="maxActionsPerStep"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Max Actions Per Step</FormLabel>
                  <FormControl>
                    <Input type="number" {...field} />
                  </FormControl>
                  <FormDescription>
                    The maximum number of actions to take within a single step.
                    This should be smaller than the total actions and is used to
                    prevent the bot from trying to spend too much time trying to
                    locate an element that may no longer exist on the page
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        </FormGroup>
        <FormGroup title="Viewport">
          <>
            <FormField
              control={form.control}
              name="viewportWidth"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Width</FormLabel>
                  <FormControl>
                    <Input type="number" {...field} />
                  </FormControl>
                  <FormDescription>
                    The width of the viewport that the tester will see in pixels
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="viewportHeight"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Height</FormLabel>
                  <FormControl>
                    <Input type="number" {...field} />
                  </FormControl>
                  <FormDescription>
                    The height of the viewport that the tester will see in
                    pixels
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        </FormGroup>
        <Button type="submit">
          Start
          {submitLoading && (
            <ReloadIcon className="ml-2 h-4 w-4 animate-spin" />
          )}
        </Button>
      </form>
    </Form>
  );
};
