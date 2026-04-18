import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import AgentRegistry from "./pages/AgentRegistry";
import SupplyGraph from "./pages/SupplyGraph";
import Coordination from "./pages/Coordination";
import Reports from "./pages/Reports";
import NotFound from "./pages/NotFound";
import { CascadeProvider } from "./state/cascadeStore";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <CascadeProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/agents" element={<AgentRegistry />} />
            <Route path="/graph" element={<SupplyGraph />} />
            <Route path="/coordination" element={<Coordination />} />
          <Route path="/reports" element={<Reports />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </CascadeProvider>
  </QueryClientProvider>
);

export default App;
