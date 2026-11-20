import { Navigate, Route, Routes } from "react-router-dom";
import AuthGate from "./components/AuthGate";
import Layout from "./components/Layout";
import BestDeals from "./pages/BestDeals";
import Dashboard from "./pages/Dashboard";
import ListingDetail from "./pages/ListingDetail";
import Results from "./pages/Results";
import SearchForm from "./pages/SearchForm";
import Searches from "./pages/Searches";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <AuthGate>
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="deals" element={<BestDeals />} />
        <Route path="searches" element={<Searches />} />
        <Route path="searches/new" element={<SearchForm />} />
        <Route path="searches/:id/edit" element={<SearchForm />} />
        <Route path="searches/:id/results" element={<Results />} />
        <Route path="listings/:id" element={<ListingDetail />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
    </AuthGate>
  );
}
