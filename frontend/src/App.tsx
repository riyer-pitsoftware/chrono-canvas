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
import { Memory } from "@/pages/Memory";
import { Timeline } from "@/pages/Timeline";
import { Review } from "@/pages/Review";
import { EvalViewer } from "@/pages/EvalViewer";
import { ModeSelector } from "@/pages/ModeSelector";

function getPage(path: string) {
  const qIdx = path.indexOf("?");
  const pathname = qIdx === -1 ? path : path.slice(0, qIdx);
  const search = qIdx === -1 ? "" : path.slice(qIdx + 1);

  if (pathname.startsWith("/audit/")) {
    const requestId = pathname.slice("/audit/".length);
    return <AuditDetail requestId={requestId} />;
  }

  if (pathname.startsWith("/review/")) {
    const requestId = pathname.slice("/review/".length);
    return <Review requestId={requestId} />;
  }

  if (pathname.startsWith("/guide/")) {
    const section = pathname.slice("/guide/".length);
    return <Guide section={section} />;
  }

  switch (pathname) {
    case "/timeline":
      return <Timeline />;
    case "/figures":
      return <FigureLibrary />;
    case "/generate": {
      const params = new URLSearchParams(search);
      const figureId = params.get("figure_id") ?? undefined;
      const mode = params.get("mode") ?? undefined;
      return <Generate figureId={figureId} mode={mode} />;
    }
    case "/validate": {
      const params = new URLSearchParams(search);
      const requestId = params.get("request_id") ?? undefined;
      return <Validate initialRequestId={requestId} />;
    }
    case "/export":
      return <Export />;
    case "/guide":
      return <Guide />;
    case "/admin":
      return <Admin />;
    case "/audit":
      return <AuditList />;
    case "/memory":
      return <Memory />;
    case "/eval":
      return <EvalViewer />;
    case "/dashboard":
      return <Dashboard />;
    default:
      return <ModeSelector />;
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
