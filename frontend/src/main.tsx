import "./globals.css";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { HomeRoute } from "./routes/Home";
import { TestEventRoute } from "./routes/TestEvent";

const container = document.getElementById("root");
const root = createRoot(container!);

const App = () => {
  return (
    <>
      <BrowserRouter>
        <Routes>
          <Route
            path="/scrape/:configId/:scrapeId"
            element={<TestEventRoute />}
          />
          <Route path="/" element={<HomeRoute />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </>
  );
};

root.render(<App />);
