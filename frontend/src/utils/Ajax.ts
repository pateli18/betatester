export class RequestError extends Error {
  response: Response;

  constructor(response: Response) {
    super(`API request failed: ${response.status} ${response.statusText}`);
    this.name = "RequestError";
    this.response = response;
  }
}

class Ajax {
  constructor() {}

  readonly defaultHeaders = {
    Accept: "application/json; gzip, deflate",
  };

  public async req<T>(opts: any): Promise<T> {
    const reqOpts = { ...opts };

    reqOpts.method = reqOpts.method || "GET";
    reqOpts.headers = reqOpts.headers || this.defaultHeaders;

    if (reqOpts.method === "POST" || reqOpts.method === "PUT") {
      if (reqOpts.body instanceof FormData) {
        reqOpts.headers = {};
      } else if (reqOpts.body && typeof reqOpts.body !== "string") {
        reqOpts.body = JSON.stringify(reqOpts.body);
        if (!reqOpts.headers["Content-Type"]) {
          reqOpts.headers["Content-Type"] = "application/json";
        }
      }
    }

    if (reqOpts.accessToken) {
      reqOpts.headers["Authorization"] = `Bearer ${reqOpts.accessToken}`;
    }

    const response = await fetch(reqOpts.url, reqOpts);

    if (!response.ok) {
      throw new RequestError(response);
    }
    if (response.status === 204) {
      return Promise.resolve({}) as Promise<T>;
    } else if (
      response.headers.get("content-type")?.includes("application/json")
    ) {
      return response.json() as Promise<T>;
    } else if (response.headers.get("content-type")?.includes("text/csv")) {
      // return filename and blob
      const contentDisposition = response.headers.get("Content-Disposition");
      const filename = contentDisposition
        ? contentDisposition.split("filename=")[1]
        : "export.csv";
      const blob = await response.blob();
      return Promise.resolve({ filename, blob }) as Promise<T>;
    } else if (response.headers.get("content-type")?.includes("image/png")) {
      return response.blob() as Promise<T>;
    } else {
      return Promise.resolve({}) as Promise<T>;
    }
  }

  readonly defaultStreamHeaders = {
    Accept: "application/x-ndjson",
    "Content-Type": "application/json",
  };

  public async *stream<T>(opts: any): AsyncGenerator<T, void, undefined> {
    const reqOpts = { ...opts };

    reqOpts.headers = reqOpts.headers || this.defaultStreamHeaders;

    if (reqOpts.body && typeof reqOpts.body !== "string") {
      reqOpts.body = JSON.stringify(reqOpts.body);
    }

    if (reqOpts.accessToken) {
      reqOpts.headers["Authorization"] = `Bearer ${reqOpts.accessToken}`;
    }

    const response = await fetch(reqOpts.url, reqOpts);

    if (!response.ok) {
      throw new RequestError(response);
    }

    // Check if the response is NDJSON
    if (
      response.headers.get("content-type")?.includes("application/x-ndjson")
    ) {
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Decode the stream chunks to text
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;

        // Process each complete JSON object
        let pos: number;
        while ((pos = buffer.indexOf("\n")) !== -1) {
          const line = buffer.slice(0, pos);
          buffer = buffer.slice(pos + 1);

          if (line.trim()) {
            try {
              const json = JSON.parse(line);
              yield json as T;
            } catch (err) {
              console.error("Error parsing JSON", err);
            }
          }
        }
      }

      // Decode the last chunk
      const remainder = decoder.decode();
      if (remainder.trim()) {
        try {
          const json = JSON.parse(remainder);
          yield json as T;
        } catch (err) {
          console.error("Error parsing JSON", err);
        }
      }
    } else {
      // Handle other content types or throw an error
      console.error(
        "Unsupported content type:",
        response.headers.get("content-type")
      );
    }
  }
}

export default new Ajax();
