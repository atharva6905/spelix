import { createBrowserRouter } from "react-router";
import RequireAuth from "@/components/RequireAuth";
import AppLayout from "@/components/AppLayout";
import ErrorBoundary from "@/components/ErrorBoundary";
import AdminPage from "@/pages/AdminPage";
import AnalysisStatusPage from "@/pages/AnalysisStatusPage";
import BetaTermsPage from "@/pages/BetaTermsPage";
import ConsentPage from "@/pages/ConsentPage";
import ExpertAnalysisDetailPage from "@/pages/ExpertAnalysisDetailPage";
import ExpertPaperUploadPage from "@/pages/ExpertPaperUploadPage";
import ExpertPortalPage from "@/pages/ExpertPortalPage";
import HistoryPage from "@/pages/HistoryPage";
import LandingPage from "@/pages/LandingPage";
import LoginPage from "@/pages/LoginPage";
import ProfilePage from "@/pages/ProfilePage";
import ResultsPage from "@/pages/ResultsPage";
import SignupPage from "@/pages/SignupPage";
import UploadPage from "@/pages/UploadPage";

const router = createBrowserRouter([
  // Public routes
  {
    path: "/",
    element: <LandingPage />,
  },
  {
    path: "/beta-terms",
    element: <BetaTermsPage />,
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
      { path: "/consent", element: <ConsentPage /> },
      { path: "/analysis/:id", element: <AnalysisStatusPage /> },
      { path: "/results/:id", element: <ResultsPage /> },
      { path: "/admin", element: <AdminPage /> },
      { path: "/expert", element: <ExpertPortalPage /> },
      { path: "/expert/analyses/:id", element: <ExpertAnalysisDetailPage /> },
      { path: "/expert/papers/upload", element: <ExpertPaperUploadPage /> },
    ],
  },
]);

export default router;
