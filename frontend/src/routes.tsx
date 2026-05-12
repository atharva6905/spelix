import { createBrowserRouter } from "react-router";
import RequireAuth from "@/components/RequireAuth";
import RequireConsent from "@/components/RequireConsent";
import AppLayout from "@/components/AppLayout";
import ErrorBoundary from "@/components/ErrorBoundary";
import AdminCoachBrainCandidatesPage from "@/pages/AdminCoachBrainCandidatesPage";
import AdminPage from "@/pages/AdminPage";
import AnalysisStatusPage from "@/pages/AnalysisStatusPage";
import BetaTermsPage from "@/pages/BetaTermsPage";
import ConsentPage from "@/pages/ConsentPage";
import ExpertAnalysisDetailPage from "@/pages/ExpertAnalysisDetailPage";
import ExpertPaperUploadPage from "@/pages/ExpertPaperUploadPage";
import ExpertPortalPage from "@/pages/ExpertPortalPage";
import ExpertThresholdsPage from "@/pages/ExpertThresholdsPage";
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
      {
        path: "/upload",
        element: (
          <RequireConsent>
            <UploadPage />
          </RequireConsent>
        ),
      },
      { path: "/history", element: <HistoryPage /> },
      { path: "/profile", element: <ProfilePage /> },
      { path: "/consent", element: <ConsentPage /> },
      {
        path: "/analysis/:id",
        element: (
          <RequireConsent>
            <AnalysisStatusPage />
          </RequireConsent>
        ),
      },
      {
        path: "/results/:id",
        element: (
          <RequireConsent>
            <ResultsPage />
          </RequireConsent>
        ),
      },
      { path: "/admin", element: <AdminPage /> },
      {
        path: "/admin/coach-brain/candidates",
        element: <AdminCoachBrainCandidatesPage />,
      },
      { path: "/expert", element: <ExpertPortalPage /> },
      { path: "/expert/analyses/:id", element: <ExpertAnalysisDetailPage /> },
      { path: "/expert/papers/upload", element: <ExpertPaperUploadPage /> },
      { path: "/expert/thresholds", element: <ExpertThresholdsPage /> },
    ],
  },
]);

export default router;
