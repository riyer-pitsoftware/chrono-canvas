import { Layout } from "@/components/layout/Layout";
import { useNavigation } from "@/stores/navigation";
import { Dashboard } from "@/pages/Dashboard";
import { FigureLibrary } from "@/pages/FigureLibrary";
import { Generate } from "@/pages/Generate";
import { Validate } from "@/pages/Validate";
import { Export } from "@/pages/Export";
import { Guide } from "@/pages/Guide";
import { Admin } from "@/pages/Admin";
import { AuditDetail } from "@/pages/AuditDetail";
import { AuditList } from "@/pages/AuditList";
import { Timeline } from "@/pages/Timeline";

function getPage(path: string) {
  if (path.startsWith("/audit/")) {
    const requestId = path.slice("/audit/".length);
    return <AuditDetail requestId={requestId} />;
  }

  if (path.startsWith("/guide/")) {
    const section = path.slice("/guide/".length);
    return <Guide section={section} />;
  }

  switch (path) {
    case "/timeline":
      return <Timeline />;
    case "/figures":
      return <FigureLibrary />;
    case "/generate":
      return <Generate />;
    case "/validate":
      return <Validate />;
    case "/export":
      return <Export />;
    case "/guide":
      return <Guide />;
    case "/admin":
      return <Admin />;
    case "/audit":
      return <AuditList />;
    default:
      return <Dashboard />;
  }
}

export default function App() {
  const { currentPath, navigate } = useNavigation();

  return (
    <Layout currentPath={currentPath} onNavigate={navigate}>
      {getPage(currentPath)}
    </Layout>
  );
}
