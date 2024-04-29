import "./globals.css";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { HomeRoute } from "./routes/Home";
import { TestEventRoute } from "./routes/TestEvent";
import { TooltipProvider } from "@/components/ui/tooltip";

const container = document.getElementById("root");
const root = createRoot(container!);

const App = () => {
  return (
    <TooltipProvider delayDuration={0}>
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
    </TooltipProvider>
  );
};

root.render(<App />);
