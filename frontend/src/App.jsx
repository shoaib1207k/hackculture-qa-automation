import { useCallback, useEffect, useState } from "react";
import {
  Alert, AppBar, Box, Button, Card, CardContent, Chip, CircularProgress, Container,
  Grid, Tab, Table, TableBody, TableCell, TableHead, TableRow, Tabs, Toolbar, Typography,
} from "@mui/material";
import { PieChart } from "@mui/x-charts/PieChart";
import { listLeads, scoreLead } from "./api";
import LeadDetail from "./LeadDetail.jsx";

export const DECISION_COLOR = { HOLD: "error", HUMAN_QA: "warning", AUTO_PASS: "success" };

function Stat({ label, value, color }) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography color="text.secondary" variant="body2">{label}</Typography>
        <Typography variant="h4" color={color}>{value}</Typography>
      </CardContent>
    </Card>
  );
}

export default function App() {
  const [tab, setTab] = useState(0);
  const [leads, setLeads] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);
  const [processing, setProcessing] = useState([]); // lead ids being scored right now

  // Every lead is listed; a lead gets its decision once the backend has processed it.
  const refresh = useCallback(
    () => listLeads().then((d) => { setLeads(d); setError(null); }).catch((e) => setError(e.message)),
    [],
  );
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, [refresh]);

  const open = (id) => { setSelected(id); setTab(1); };

  const process = async (id) => {
    setProcessing((p) => [...p, id]);
    try {
      const result = await scoreLead(id);
      // A scoring failure comes back as a result with `error`; it is not saved.
      if (result.error) {
        setError(`Lead ${id} could not be processed (${result.error}). It was sent to a human and not saved; try again.`);
      }
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setProcessing((p) => p.filter((x) => x !== id));
    }
  };
  const scored = leads.filter((l) => l.score);
  const count = (d) => scored.filter((l) => l.score.decision === d).length;

  return (
    <>
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>QA Automation</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mr: 2 }}>
            Updates automatically
          </Typography>
          <Button variant="outlined" onClick={refresh}>Refresh</Button>
        </Toolbar>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ px: 2 }}>
          <Tab label="Overview" />
          <Tab label="Lead detail" disabled={!selected} />
        </Tabs>
      </AppBar>

      <Container maxWidth="xl" sx={{ py: 3 }}>
        {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}

        {tab === 0 && (
          <Box>
            <Grid container spacing={2} sx={{ mb: 3 }}>
              <Grid size={{ xs: 6, md: 3 }}><Stat label="Leads" value={leads.length} /></Grid>
              <Grid size={{ xs: 6, md: 3 }}><Stat label="HOLD" value={count("HOLD")} color="error" /></Grid>
              <Grid size={{ xs: 6, md: 3 }}><Stat label="HUMAN_QA" value={count("HUMAN_QA")} color="warning.main" /></Grid>
              <Grid size={{ xs: 6, md: 3 }}><Stat label="AUTO_PASS" value={count("AUTO_PASS")} color="success.main" /></Grid>
            </Grid>

            {scored.length > 0 && (
              <Card variant="outlined" sx={{ mb: 3 }}>
                <PieChart height={220} series={[{ innerRadius: 50, data: [
                  { id: 0, label: "HOLD", value: count("HOLD"), color: "#d32f2f" },
                  { id: 1, label: "HUMAN_QA", value: count("HUMAN_QA"), color: "#ed6c02" },
                  { id: 2, label: "AUTO_PASS", value: count("AUTO_PASS"), color: "#2e7d32" },
                ] }]} />
              </Card>
            )}

            <Card variant="outlined">
              <Table>
                <TableHead>
                  <TableRow>
                    {["Lead", "Customer", "Retailer", "Call date", "Decision", "Fails", "Uncertain", ""].map((h) => (
                      <TableCell key={h}>{h}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {leads.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={8} align="center" sx={{ py: 6, color: "text.secondary" }}>
                        No leads found.
                      </TableCell>
                    </TableRow>
                  )}
                  {leads.map((l) => {
                    const vs = l.score?.verdicts ?? [];
                    const busy = processing.includes(l.lead_id);
                    return (
                      <TableRow key={l.lead_id} hover={!!l.score}
                                sx={{ cursor: l.score ? "pointer" : "default" }}
                                onClick={l.score ? () => open(l.lead_id) : undefined}>
                        <TableCell>{l.lead_id}</TableCell>
                        <TableCell>{l.customer_name}</TableCell>
                        <TableCell>{l.retailer_id}</TableCell>
                        <TableCell>{l.call_date}</TableCell>
                        <TableCell>
                          {l.score
                            ? <Chip size="small" label={l.score.decision} color={DECISION_COLOR[l.score.decision]} />
                            : <Chip size="small" label="not processed" variant="outlined" />}
                        </TableCell>
                        <TableCell>{l.score ? vs.filter((v) => v.verdict === "fail").length : "–"}</TableCell>
                        <TableCell>{l.score ? vs.filter((v) => v.verdict === "uncertain").length : "–"}</TableCell>
                        <TableCell align="right">
                          {l.score ? (
                            <Button size="small" onClick={() => open(l.lead_id)}>View details</Button>
                          ) : (
                            <Button size="small" variant="contained" disabled={busy}
                                    startIcon={busy && <CircularProgress size={14} color="inherit" />}
                                    onClick={(e) => { e.stopPropagation(); process(l.lead_id); }}>
                              {busy ? "Processing…" : "Process"}
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </Card>
          </Box>
        )}

        {tab === 1 && selected && <LeadDetail key={selected} leadId={selected} onScored={refresh} />}
      </Container>
    </>
  );
}
