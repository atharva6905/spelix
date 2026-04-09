import { createBrowserRouter } from "react-router";
import RequireAuth from "@/components/RequireAuth";
import AppLayout from "@/components/AppLayout";
import ErrorBoundary from "@/components/ErrorBoundary";
import AdminPage from "@/pages/AdminPage";
import AnalysisStatusPage from "@/pages/AnalysisStatusPage";
import HistoryPage from "@/pages/HistoryPage";
import HomePage from "@/pages/HomePage";
import LoginPage from "@/pages/LoginPage";
import ProfilePage from "@/pages/ProfilePage";
import ResultsPage from "@/pages/ResultsPage";
import SignupPage from "@/pages/SignupPage";
import UploadPage from "@/pages/UploadPage";

const router = createBrowserRouter([
  // Public routes
  {
    path: "/",
    element: <HomePage />,
  },
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/signup",
    element: <SignupPage />,
  },

  // Authenticated routes with shared nav layout
  {
    element: (
      <RequireAuth>
        <ErrorBoundary>
          <AppLayout />
        </ErrorBoundary>
      </RequireAuth>
    ),
    children: [
      { path: "/upload", element: <UploadPage /> },
      { path: "/history", element: <HistoryPage /> },
      { path: "/profile", element: <ProfilePage /> },
      { path: "/analysis/:id", element: <AnalysisStatusPage /> },
      { path: "/results/:id", element: <ResultsPage /> },
      { path: "/admin", element: <AdminPage /> },
    ],
  },
]);

export default router;
