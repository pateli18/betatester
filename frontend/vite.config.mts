import { UserConfig, defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const config: UserConfig = {
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src/shadcn"),
    },
  },
};
const build = process.env["BUILD"] === "true";

if (!build) {
  config.server = {
    host: "127.0.0.1",
    port: 3000,
    open: "http://localhost:3000/",
    proxy: {
      "/api": "http://localhost:8080/",
      "/data": "http://localhost:8080/",
    },
  };
}
// https://vitejs.dev/config/
export default defineConfig(config);
