import { useEffect, useRef, useState } from "react";
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, AlertTitle, Box, Button, Card,
  CardContent, Chip, CircularProgress, Divider, Stack, Typography,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { getLead, scoreLead } from "./api";
import {
  CRM_GROUPS, DECISION_INFO, SPEAKER_LABEL, TYPE_LABEL, effectiveVerdict, formatDate, formatValue,
  humanize, isLowConfidence, mmss, timeRange, verdictInfo,
} from "./labels";

// Colours from least to most severe. A transcript line cited by several checks takes the worst.
const SEVERITY = ["success", "info", "warning", "error"];
const LEGEND = { error: "Failed", warning: "Unclear", info: "Note", success: "Passed" };

const RESULT_WORD = { pass: "passed", fail: "failed", uncertain: "unclear" };

// Failed critical checks first, then unclear ones, then non-critical notes.
const attentionRank = (v, threshold) => {
  const verdict = effectiveVerdict(v, threshold);
  return verdict === "fail" && v.critical ? 0 : verdict === "uncertain" ? 1 : 2;
};

function CheckRow({ v, threshold, segById, onJump }) {
  const info = verdictInfo(v, threshold);
  const low = isLowConfidence(v, threshold);
  const pct = Math.round(v.confidence * 100);
  const when = timeRange(v.timestamp_start, v.timestamp_end);
  return (
    <Accordion variant="outlined" disableGutters>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap", rowGap: 0.5 }}>
          <Chip size="small" label={info.label} color={info.color} sx={{ minWidth: 72 }} />
          <Typography sx={{ fontWeight: 500 }}>{v.check_name}</Typography>
          {v.critical && <Chip size="small" variant="outlined" color="error" label="Critical" />}
          <Chip size="small" variant="outlined" label={TYPE_LABEL[v.check_type]} />
          <Typography variant="body2" color="text.secondary">
            {v.verdict === "uncertain" ? "Could not be confirmed" : low ? `Low confidence (${pct}%)` : `${pct}% confident`}
            {when ? ` · at ${when}` : ""}
          </Typography>
        </Stack>
      </AccordionSummary>
      <AccordionDetails>
        {low && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            This check came out as {RESULT_WORD[v.verdict]}, but the confidence ({pct}%) is below the{" "}
            {Math.round(threshold * 100)}% needed, so a person should confirm it before the sale goes through.
          </Alert>
        )}
        <Typography variant="subtitle2">Why</Typography>
        <Typography sx={{ mb: 2 }}>{v.reasoning}</Typography>

        {v.evidence_text ? (
          <>
            <Typography variant="subtitle2">What was said{when ? ` (${when})` : ""}</Typography>
            <Typography sx={{ mt: 0.5, mb: 1.5, pl: 2, borderLeft: 3, borderColor: "divider" }} color="text.secondary">
              {v.evidence_text}
            </Typography>
          </>
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            No matching line was found in the transcript.
          </Typography>
        )}

        {v.evidence_segment_ids.length > 0 && (
          <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap", rowGap: 0.5 }}>
            <Typography variant="caption" color="text.secondary">Show in transcript:</Typography>
            {v.evidence_segment_ids.map((id) => {
              const s = segById[id];
              return (
                <Chip key={id} size="small" clickable variant="outlined" onClick={() => onJump(id)}
                      label={s ? `${mmss(s.start)} · ${SPEAKER_LABEL[s.speaker]}` : id} />
              );
            })}
          </Stack>
        )}
      </AccordionDetails>
    </Accordion>
  );
}

function CheckGroup({ title, checks, threshold, segById, onJump }) {
  if (!checks.length) return null;
  return (
    <Box sx={{ mb: 3 }}>
      <Typography variant="h6" gutterBottom>{title} · {checks.length}</Typography>
      {checks.map((v) => <CheckRow key={v.check_id} v={v} threshold={threshold} segById={segById} onJump={onJump} />)}
    </Box>
  );
}

function CrmRecord({ crm }) {
  const listed = new Set(CRM_GROUPS.flatMap(([, keys]) => keys));
  const other = Object.keys(crm).filter((k) => !listed.has(k));
  const groups = [...CRM_GROUPS, ["Other", other]]
    .map(([title, keys]) => [title, keys.filter((k) => k in crm)])
    .filter(([, keys]) => keys.length);
  return (
    <Card variant="outlined">
      <CardContent>
        {groups.map(([title, keys], i) => (
          <Box key={title} sx={{ mb: i < groups.length - 1 ? 2 : 0 }}>
            {i > 0 && <Divider sx={{ mb: 2 }} />}
            <Typography variant="subtitle2" gutterBottom>{title}</Typography>
            {keys.map((k) => (
              <Box key={k} sx={{ display: "flex", gap: 2, py: 0.25 }}>
                <Typography variant="body2" color="text.secondary" sx={{ width: "42%", flexShrink: 0 }}>
                  {humanize(k)}
                </Typography>
                <Typography variant="body2" sx={{ wordBreak: "break-word" }}>{formatValue(crm[k])}</Typography>
              </Box>
            ))}
          </Box>
        ))}
      </CardContent>
    </Card>
  );
}

export default function LeadDetail({ leadId, onScored }) {
  const [lead, setLead] = useState(null);
  const [score, setScore] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [focused, setFocused] = useState(null);
  const segRefs = useRef({});

  useEffect(() => {
    getLead(leadId).then((d) => { setLead(d); setScore(d.score); }).catch((e) => setError(e.message));
  }, [leadId]);

  const run = async (force) => {
    setBusy(true);
    setError(null);
    try {
      setScore(await scoreLead(leadId, force));
      onScored();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const jumpTo = (id) => {
    segRefs.current[id]?.scrollIntoView({ behavior: "smooth", block: "center" });
    setFocused(id);
    setTimeout(() => setFocused((f) => (f === id ? null : f)), 2500);
  };

  if (!lead) return error ? <Alert severity="error">{error}</Alert> : <CircularProgress />;

  const verdicts = score?.verdicts ?? [];
  const threshold = score?.confidence_threshold ?? 0.75;
  // segment id -> colour of the worst result among the checks that cite it
  const segColor = {};
  for (const v of verdicts) {
    const color = verdictInfo(v, threshold).color;
    for (const id of v.evidence_segment_ids) {
      if (!segColor[id] || SEVERITY.indexOf(color) > SEVERITY.indexOf(segColor[id])) segColor[id] = color;
    }
  }
  const legend = SEVERITY.filter((c) => Object.values(segColor).includes(c)).reverse();
  const segById = Object.fromEntries(lead.transcript.map((s) => [s.segment_id, s]));
  const isPassed = (v) => effectiveVerdict(v, threshold) === "pass";
  const needsAttention = verdicts.filter((v) => !isPassed(v))
    .sort((a, b) => attentionRank(a, threshold) - attentionRank(b, threshold));
  const passed = verdicts.filter(isPassed);
  const decision = score && DECISION_INFO[score.decision];

  return (
    <Stack spacing={3}>
      {error && <Alert severity="error">{error}</Alert>}

      <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h5">
            Lead {leadId}{lead.customer_name ? ` · ${lead.customer_name}` : ""}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Retailer {lead.retailer_id}
            {score ? ` · Checklist ${score.checklist_version}` : ""} · Call date {formatDate(lead.call_date)}
          </Typography>
        </Box>
        <Button variant="outlined" onClick={() => run(!!score)} disabled={busy}
                startIcon={busy && <CircularProgress size={16} />}>
          {score ? "Re-score" : "Score this lead"}
        </Button>
      </Stack>

      {score && decision && (
        <Alert severity={decision.severity}>
          <AlertTitle>{decision.title}</AlertTitle>
          <Typography variant="body2" sx={{ mb: 1 }}>{decision.text}</Typography>
          <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
            {score.reasons.map((r) => <li key={r}>{r}</li>)}
          </Box>
          {score.error && <Typography variant="body2" sx={{ mt: 1 }}>Error: {score.error}</Typography>}
        </Alert>
      )}

      {score && (
        <Box>
          <CheckGroup title="Needs attention" checks={needsAttention} threshold={threshold} segById={segById} onJump={jumpTo} />
          <CheckGroup title="Passed" checks={passed} threshold={threshold} segById={segById} onJump={jumpTo} />
        </Box>
      )}

      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", md: "7fr 5fr" } }}>
        <Box>
          <Typography variant="h6">Transcript</Typography>
          <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap", rowGap: 0.5, mb: 1 }}>
            <Typography variant="body2" color="text.secondary">Highlighted lines are the evidence behind a check:</Typography>
            {legend.map((c) => <Chip key={c} size="small" variant="outlined" color={c} label={LEGEND[c]} />)}
          </Stack>
        </Box>
        <Typography variant="h6">CRM record</Typography>

        {/* On wide screens the transcript card is taken out of the row's height (absolute), so the
            row is exactly as tall as the CRM record and both cards line up top and bottom; the
            transcript scrolls inside its card. When stacked, it gets a fixed height instead. */}
        <Box sx={{ position: "relative", height: { xs: "60vh", md: "auto" } }}>
          <Card variant="outlined" sx={{ position: "absolute", inset: 0, overflowY: "auto" }}>
            {lead.transcript.map((s) => {
              const c = segColor[s.segment_id];
              const isFocused = focused === s.segment_id;
              return (
                <Box key={s.segment_id} ref={(el) => { segRefs.current[s.segment_id] = el; }}
                     sx={{
                       px: 2, py: 1, transition: "background-color .3s", borderLeft: 4,
                       borderColor: c ? `${c}.main` : "transparent",
                       bgcolor: isFocused ? `${c}.main` : c ? (t) => alpha(t.palette[c].main, 0.16) : "transparent",
                       color: isFocused ? `${c}.contrastText` : "inherit",
                       "& .MuiTypography-root": isFocused ? { color: "inherit" } : undefined,
                     }}>
                  <Typography variant="caption" color="text.secondary">
                    {SPEAKER_LABEL[s.speaker]} · {mmss(s.start)}
                  </Typography>
                  <Typography variant="body2">{s.text}</Typography>
                </Box>
              );
            })}
          </Card>
        </Box>
        <CrmRecord crm={lead.crm} />
      </Box>
    </Stack>
  );
}
