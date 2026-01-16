import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import PipelineHealth from './pages/PipelineHealth';
import Strategies from './pages/Strategies';
import Trading from './pages/Trading';
import System from './pages/System';

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
            <Route path="/strategies" element={<Strategies />} />
            <Route path="/trading" element={<Trading />} />
            <Route path="/system" element={<System />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
