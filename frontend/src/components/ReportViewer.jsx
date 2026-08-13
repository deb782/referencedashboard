import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Download } from "lucide-react";
import { Modal } from "@/components/ui";
import { fetchPdfUrl, downloadFile, apiError } from "@/lib/api";

export function ReportViewer({ unitId, plotNumber, onClose }) {
  const [url, setUrl] = useState(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let obj;
    (async () => {
      try { obj = await fetchPdfUrl(`/units/${unitId}/payment-report`); setUrl(obj); }
      catch (e) { setErr(true); toast.error(apiError(e)); }
    })();
    return () => { if (obj) window.URL.revokeObjectURL(obj); };
  }, [unitId]);

  const dl = async () => {
    try { await downloadFile(`/units/${unitId}/payment-report`, `Payment_Report_${plotNumber}.pdf`); }
    catch (e) { toast.error(apiError(e)); }
  };

  return (
    <Modal size="2xl" title={`Payment report · Plot ${plotNumber}`} subtitle="Plot-wise statement of billing, receipts and balances." onClose={onClose}
      footer={<>
        <button onClick={onClose} className="btn-secondary">Close</button>
        <button onClick={dl} className="btn-primary" data-testid="report-download"><Download className="w-4 h-4" /> Download PDF</button>
      </>}>
      {!url && !err && <div className="h-[70vh] flex items-center justify-center text-sm text-ink2">Generating report…</div>}
      {err && <div className="h-[40vh] flex items-center justify-center text-sm text-bad">Could not load the report.</div>}
      {url && <iframe title="Payment report" src={url} className="w-full h-[70vh] rounded-md border border-line bg-white" data-testid="report-iframe" />}
    </Modal>
  );
}
