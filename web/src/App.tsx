import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import PipelineHealth from './pages/PipelineHealth';
import Rankings from './pages/Rankings';
import Strategies from './pages/Strategies';
import Templates from './pages/Templates';
import Validation from './pages/Validation';
import Trading from './pages/Trading';
import SystemTasks from './pages/SystemTasks';
import Logs from './pages/Logs';
import Settings from './pages/Settings';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Overview />} />
            <Route path="/pipeline" element={<PipelineHealth />} />
            <Route path="/rankings" element={<Rankings />} />
            <Route path="/strategies" element={<Strategies />} />
            <Route path="/templates" element={<Templates />} />
            <Route path="/validation" element={<Validation />} />
            <Route path="/trading" element={<Trading />} />
            <Route path="/system-tasks" element={<SystemTasks />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
