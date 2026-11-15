from datetime import datetime, timedelta
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.database import get_db_connection

STRIP_INTERNAL_TAGS_RE = re.compile(
    r"<think\b[^>]*>[\s\S]*?</think>"
    r"|<monologue\b[^>]*>[\s\S]*?</monologue>"
    r"|<property_update\b[^>]*>(?:[\s\S]*?</property_update>)?",
    re.IGNORECASE,
)

DEFAULT_LIMIT = 5
MAX_LIMIT = 15
PREVIEW_CHARS = 150
DEFAULT_CONTEXT_TURNS = 4
MAX_CONTEXT_TURNS = 8
VALID_TARGETS = {"all", "journals", "conversations"}
VALID_SOURCE_TYPES = {"journal", "conversation"}


def strip_internal_tags(text: Optional[str]) -> str:
    """Remove internal reasoning and state tags before surfacing historical records."""
    if not text:
        return ""
    cleaned = STRIP_INTERNAL_TAGS_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _truncate_preview(text: str, max_chars: int = PREVIEW_CHARS) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rstrip() + "..."


def _escape_like(term: str) -> str:
    """Escape SQLite LIKE wildcards so literal '%', '_', and '\\' match verbatim."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


DATE_DAY_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DATE_MONTH_RE = re.compile(r"\d{4}-\d{2}")


def _build_date_clauses(
    date_range: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    ts_expr: str = "timestamp",
) -> Tuple[List[str], List[Any], Optional[str]]:
    """Build parameterized SQL date clauses from date_range and/or inclusive start_date/end_date."""
    norm_ts = f"replace(COALESCE({ts_expr}, ''), 'T', ' ')"
    day_expr = f"substr({norm_ts}, 1, 10)"
    clauses: List[str] = []
    params: List[Any] = []

    if date_range and str(date_range).strip():
        dr = str(date_range).strip().lower()
        if dr == "recent_7d":
            cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            clauses.append(f"{norm_ts} >= ?")
            params.append(cutoff)
        elif dr == "recent_30d":
            cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            clauses.append(f"{norm_ts} >= ?")
            params.append(cutoff)
        elif DATE_DAY_RE.fullmatch(dr):
            clauses.append(f"{day_expr} = ?")
            params.append(dr)
        elif DATE_MONTH_RE.fullmatch(dr):
            clauses.append(f"{norm_ts} LIKE ?")
            params.append(f"{dr}-%")
        else:
            return [], [], (
                f"[Error] Invalid date_range '{date_range}'. "
                "Expected 'YYYY-MM-DD', 'YYYY-MM', 'recent_7d', or 'recent_30d'."
            )

    sd = str(start_date).strip() if start_date and str(start_date).strip() else None
    ed = str(end_date).strip() if end_date and str(end_date).strip() else None
    if sd and not DATE_DAY_RE.fullmatch(sd):
        return [], [], f"[Error] Invalid start_date '{start_date}'. Expected 'YYYY-MM-DD'."
    if ed and not DATE_DAY_RE.fullmatch(ed):
        return [], [], f"[Error] Invalid end_date '{end_date}'. Expected 'YYYY-MM-DD'."
    if sd and ed and sd > ed:
        return [], [], f"[Error] start_date '{sd}' cannot be later than end_date '{ed}'."

    if sd:
        clauses.append(f"{day_expr} >= ?")
        params.append(sd)
    if ed:
        clauses.append(f"{day_expr} <= ?")
        params.append(ed)

    return clauses, params, None


class MemorySearchEngine:
    """Read-only search engine over SQLite memory_logs and chat_messages."""

    @staticmethod
    def _normalize_limit(
        limit: Any,
        default: int = DEFAULT_LIMIT,
        ceiling: int = MAX_LIMIT,
    ) -> int:
        try:
            val = int(limit) if limit is not None else default
        except (TypeError, ValueError):
            return default
        return max(1, min(val, ceiling))

    def execute(self, params: Dict[str, Any]) -> str:
        mode = (params.get("mode") or "search").strip().lower()
        target = (params.get("target") or "all").strip().lower()
        if mode == "search":
            return self.search(
                query=(params.get("query") or "").strip(),
                target=target,
                date_range=params.get("date_range"),
                start_date=params.get("start_date"),
                end_date=params.get("end_date"),
                limit=params.get("limit"),
            )
        if mode == "timeline":
            return self.timeline(
                date_range=params.get("date_range"),
                start_date=params.get("start_date"),
                end_date=params.get("end_date"),
                target=target,
                query=(params.get("query") or "").strip(),
                limit=params.get("limit"),
            )
        if mode == "expand":
            return self.expand(
                source_type=(params.get("source_type") or "").strip().lower(),
                record_id=params.get("record_id"),
                context_turns=params.get("context_turns"),
            )
        return f"[Error] Unsupported mode '{mode}'. Supported modes: search, timeline, expand."

    def calendar(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        date_range: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> str:
        """Aggregate per-day conversation session counts, session titles, and diary counts."""
        log_date_clauses, log_date_params, date_err = _build_date_clauses(
            date_range=date_range,
            start_date=start_date,
            end_date=end_date,
            ts_expr="timestamp",
        )
        if date_err:
            return date_err

        msg_date_clauses, msg_date_params, _ = _build_date_clauses(
            date_range=date_range,
            start_date=start_date,
            end_date=end_date,
            ts_expr="m.timestamp",
        )
        capped_days = self._normalize_limit(limit, default=15, ceiling=31)

        day_map: Dict[str, Dict[str, Any]] = {}

        def _ensure_day(day: str) -> Dict[str, Any]:
            if day not in day_map:
                day_map[day] = {"journals": 0, "msgs": 0, "sessions": {}}
            return day_map[day]

        conn = get_db_connection()
        try:
            log_clauses = [
                "COALESCE(status, 'active') != 'archived'",
                "length(trim(COALESCE(timestamp, ''))) >= 10",
                *log_date_clauses,
            ]
            log_rows = conn.execute(
                f"""
                SELECT substr(replace(COALESCE(timestamp, ''), 'T', ' '), 1, 10) AS day, COUNT(*) AS cnt
                FROM memory_logs
                WHERE {' AND '.join(log_clauses)}
                GROUP BY day
                """,
                log_date_params,
            ).fetchall()
            for row in log_rows:
                if row["day"]:
                    _ensure_day(row["day"])["journals"] = row["cnt"]

            msg_clauses = [
                "m.role IN ('user', 'assistant')",
                "length(trim(COALESCE(m.timestamp, ''))) >= 10",
                *msg_date_clauses,
            ]
            msg_rows = conn.execute(
                f"""
                SELECT
                    substr(replace(COALESCE(m.timestamp, ''), 'T', ' '), 1, 10) AS day,
                    COALESCE(m.session_id, 'default') AS sid,
                    COALESCE(NULLIF(trim(s.title), ''), m.session_id, 'untitled') AS title,
                    COUNT(*) AS msg_cnt
                FROM chat_messages m
                LEFT JOIN chat_sessions s ON s.id = m.session_id
                WHERE {' AND '.join(msg_clauses)}
                GROUP BY day, sid
                ORDER BY day ASC, MIN(m.id) ASC
                """,
                msg_date_params,
            ).fetchall()
            for row in msg_rows:
                day = row["day"]
                if not day:
                    continue
                entry = _ensure_day(day)
                entry["msgs"] += row["msg_cnt"]
                entry["sessions"][row["sid"]] = _truncate_preview(str(row["title"]), max_chars=40)
        finally:
            conn.close()

        if not day_map:
            return self._build_empty_notice(
                date_range=date_range,
                start_date=start_date,
                end_date=end_date,
            )

        selected_days = sorted(sorted(day_map.keys(), reverse=True)[:capped_days])
        lines: List[str] = []
        for day in selected_days:
            entry = day_map[day]
            sess_cnt = len(entry["sessions"])
            msg_cnt = entry["msgs"]
            j_cnt = entry["journals"]
            counts = (
                f"{sess_cnt} session{'s' if sess_cnt != 1 else ''}, "
                f"{msg_cnt} msg{'s' if msg_cnt != 1 else ''}, "
                f"{j_cnt} journal{'s' if j_cnt != 1 else ''}"
            )
            titles = list(entry["sessions"].values())[:4]
            title_part = f" | topics: {', '.join(repr(t) for t in titles)}" if titles else ""
            if len(entry["sessions"]) > 4:
                title_part += f" (+{len(entry['sessions']) - 4} more)"
            lines.append(f"- [{day}] {counts}{title_part}")

        meta: List[str] = []
        if date_range:
            meta.append(f"date_range: {date_range!r}")
        if start_date:
            meta.append(f"start_date: {start_date!r}")
        if end_date:
            meta.append(f"end_date: {end_date!r}")
        meta.append(f"active_days: {len(selected_days)}")
        header = f"[Memory Calendar Overview | {' | '.join(meta)}]"
        footer = 'Note: Call get_memory_timeline with date_range="YYYY-MM-DD" to inspect records for a specific day.'
        return "\n".join([header, *lines, footer])

    @staticmethod
    def _normalize_context_turns(context_turns: Any) -> int:
        try:
            val = int(context_turns) if context_turns is not None else DEFAULT_CONTEXT_TURNS
        except (TypeError, ValueError):
            return DEFAULT_CONTEXT_TURNS
        return max(0, min(val, MAX_CONTEXT_TURNS))

    def expand(
        self,
        source_type: str,
        record_id: Any,
        context_turns: Optional[int] = None,
    ) -> str:
        if source_type not in VALID_SOURCE_TYPES:
            return "[Error] 'source_type' must be 'journal' or 'conversation' when mode='expand'."
        try:
            rec_id = int(record_id)
        except (TypeError, ValueError):
            return "[Error] A valid integer 'record_id' is required when mode='expand'."

        turns = self._normalize_context_turns(context_turns)
        conn = get_db_connection()
        try:
            if source_type == "journal":
                row = conn.execute(
                    """
                    SELECT id, timestamp, level, summary, content, session_id
                    FROM memory_logs
                    WHERE id = ? AND COALESCE(status, 'active') != 'archived'
                    """,
                    (rec_id,),
                ).fetchone()
                if not row:
                    return f"[No memory record found for journal #{rec_id}.]"

                parts = [f"[Memory Detail | journal #{row['id']} | {row['timestamp']} | level:{row['level']}]"]
                if row["summary"]:
                    parts.append(f"Summary: {strip_internal_tags(row['summary'])}")
                if row["content"]:
                    parts.append(f"Content:\n{strip_internal_tags(row['content'])}")
                return "\n".join(parts)

            target_row = conn.execute(
                """
                SELECT id, session_id
                FROM chat_messages
                WHERE id = ? AND role IN ('user', 'assistant')
                """,
                (rec_id,),
            ).fetchone()
            if not target_row:
                return f"[No memory record found for conversation #{rec_id}.]"

            session_id = target_row["session_id"]
            before_rows = list(
                reversed(
                    conn.execute(
                        """
                        SELECT id, role, content, timestamp
                        FROM chat_messages
                        WHERE session_id = ? AND role IN ('user', 'assistant') AND id < ?
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (session_id, rec_id, turns),
                    ).fetchall()
                )
            )
            after_rows = conn.execute(
                """
                SELECT id, role, content, timestamp
                FROM chat_messages
                WHERE session_id = ? AND role IN ('user', 'assistant') AND id >= ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (session_id, rec_id, turns + 1),
            ).fetchall()

            window_rows = before_rows + list(after_rows)
            lines = [f"[Memory Detail | conversation #{rec_id} | session:{session_id} | messages:{len(window_rows)}]"]
            for row in window_rows:
                clean = strip_internal_tags(row["content"])
                marker = " *match*" if row["id"] == rec_id else ""
                lines.append(f"- [conversation #{row['id']} | {row['timestamp']} | {row['role']}{marker}]\n  {clean}")
            return "\n".join(lines)
        finally:
            conn.close()

    def search(
        self,
        query: str,
        target: str = "all",
        date_range: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> str:
        if not query or not str(query).strip():
            return "[Error] 'query' is required for search_memory."
        return self._run_preview_query(
            mode="search",
            query=str(query).strip(),
            target=target,
            date_range=date_range,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    def timeline(
        self,
        date_range: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        target: str = "all",
        query: str = "",
        limit: Optional[int] = None,
    ) -> str:
        return self._run_preview_query(
            mode="timeline",
            query=query,
            target=target,
            date_range=date_range,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    def _run_preview_query(
        self,
        mode: str,
        query: str,
        target: str,
        date_range: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        limit: Optional[int],
    ) -> str:
        if target not in VALID_TARGETS:
            return f"[Error] Invalid target '{target}'. Expected one of: all, journals, conversations."

        date_clauses, date_params, date_err = _build_date_clauses(
            date_range=date_range,
            start_date=start_date,
            end_date=end_date,
        )
        if date_err:
            return date_err

        capped_limit = self._normalize_limit(limit)
        lines: List[str] = []

        conn = get_db_connection()
        try:
            if target in ("all", "journals"):
                clauses = ["COALESCE(status, 'active') != 'archived'"]
                sql_params: List[Any] = []
                if query:
                    like_pat = _escape_like(query)
                    clauses.append("(COALESCE(summary, '') LIKE ? ESCAPE '\\' OR COALESCE(content, '') LIKE ? ESCAPE '\\')")
                    sql_params.extend([like_pat, like_pat])
                if date_clauses:
                    clauses.extend(date_clauses)
                    sql_params.extend(date_params)
                sql_params.append(capped_limit)

                rows = conn.execute(
                    f"""
                    SELECT id, timestamp, level, summary, content
                    FROM memory_logs
                    WHERE {' AND '.join(clauses)}
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    sql_params,
                ).fetchall()
                for row in rows:
                    text = strip_internal_tags(row["summary"] or row["content"])
                    lines.append(
                        f"- [journal #{row['id']} | {row['timestamp']}] {_truncate_preview(text)}"
                    )

            if target in ("all", "conversations"):
                remaining = capped_limit - len(lines) if target == "all" else capped_limit
                if remaining > 0:
                    clauses = ["role IN ('user', 'assistant')"]
                    sql_params = []
                    if query:
                        clauses.append("COALESCE(content, '') LIKE ? ESCAPE '\\'")
                        sql_params.append(_escape_like(query))
                    if date_clauses:
                        clauses.extend(date_clauses)
                        sql_params.extend(date_params)
                    sql_params.append(max(remaining * 2, capped_limit))

                    rows = conn.execute(
                        f"""
                        SELECT id, session_id, role, content, timestamp
                        FROM chat_messages
                        WHERE {' AND '.join(clauses)}
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        sql_params,
                    ).fetchall()
                    query_lower = query.lower()
                    for row in rows:
                        clean = strip_internal_tags(row["content"])
                        if query_lower and query_lower not in clean.lower():
                            continue
                        if not clean:
                            continue
                        lines.append(
                            f"- [conversation #{row['id']} | session:{row['session_id']} | {row['timestamp']} | {row['role']}] {_truncate_preview(clean)}"
                        )
                        if len(lines) >= capped_limit:
                            break
        finally:
            conn.close()

        if not lines:
            return self._build_empty_notice(
                date_range=date_range,
                start_date=start_date,
                end_date=end_date,
                target=target,
            )

        meta = [f"mode: {mode}"]
        if query:
            meta.append(f"query: {query!r}")
        if date_range:
            meta.append(f"date_range: {date_range!r}")
        if start_date:
            meta.append(f"start_date: {start_date!r}")
        if end_date:
            meta.append(f"end_date: {end_date!r}")
        meta.append(f"target: {target}")
        meta.append(f"hits: {len(lines)}")
        header = f"[Memory Search Results | {' | '.join(meta)}]"
        footer = "Note: Call expand_memory with source_type and record_id to inspect full details if needed."
        return "\n".join([header, *lines, footer])

    @staticmethod
    def _collect_bucket_counts(
        conn,
        bucket_len: int,
        target: str = "all",
        prefix: Optional[str] = None,
        extra_clauses: Optional[List[str]] = None,
        extra_params: Optional[List[Any]] = None,
    ) -> Dict[str, Tuple[int, int]]:
        """Aggregate (journal_count, message_count) keyed by date prefix ('YYYY-MM-DD', 'YYYY-MM', or 'YYYY')."""
        norm_ts = "replace(COALESCE(timestamp, ''), 'T', ' ')"
        bucket_expr = f"substr({norm_ts}, 1, {bucket_len})"
        counts: Dict[str, List[int]] = {}

        def _query_table(table: str, base_where: str, idx: int) -> None:
            clauses = [base_where, f"length(trim(COALESCE(timestamp, ''))) >= {bucket_len}"]
            params: List[Any] = []
            if prefix:
                clauses.append(f"{norm_ts} LIKE ?")
                params.append(f"{prefix}%")
            if extra_clauses:
                clauses.extend(extra_clauses)
                params.extend(extra_params or [])
            rows = conn.execute(
                f"""
                SELECT {bucket_expr} AS bucket, COUNT(*) AS cnt
                FROM {table}
                WHERE {' AND '.join(clauses)}
                GROUP BY bucket
                ORDER BY bucket ASC
                """,
                params,
            ).fetchall()
            for row in rows:
                b = row["bucket"]
                if not b:
                    continue
                if b not in counts:
                    counts[b] = [0, 0]
                counts[b][idx] += row["cnt"]

        if target in ("all", "journals"):
            _query_table("memory_logs", "COALESCE(status, 'active') != 'archived'", 0)
        if target in ("all", "conversations"):
            _query_table("chat_messages", "role IN ('user', 'assistant')", 1)

        return {k: (v[0], v[1]) for k, v in sorted(counts.items())}

    def _build_empty_notice(
        self,
        date_range: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        target: str = "all",
    ) -> str:
        """Build an objective empty notice with progressive active date/month/year hints when date-scoped."""
        dr = str(date_range).strip() if date_range and str(date_range).strip() else None
        sd = str(start_date).strip() if start_date and str(start_date).strip() else None
        ed = str(end_date).strip() if end_date and str(end_date).strip() else None
        if not (dr or sd or ed):
            return "[No memory records found matching the given criteria.]"

        scope_label = dr or (f"{sd or '...'}..{ed or '...'}")
        anchor_month: Optional[str] = None
        anchor_year: Optional[str] = None
        if dr and DATE_DAY_RE.fullmatch(dr):
            anchor_month = dr[:7]
            anchor_year = dr[:4]
        elif dr and DATE_MONTH_RE.fullmatch(dr):
            anchor_year = dr[:4]
        elif sd and ed and sd[:7] == ed[:7]:
            anchor_month = sd[:7]
            anchor_year = sd[:4]
        elif sd or ed:
            anchor_year = (sd or ed)[:4]
        elif dr and dr.lower() in ("recent_7d", "recent_30d"):
            now = datetime.now()
            anchor_month = now.strftime("%Y-%m")
            anchor_year = now.strftime("%Y")

        conn = get_db_connection()
        try:
            def _fmt(buckets: Dict[str, Tuple[int, int]]) -> str:
                return ", ".join(f"{b} ({j + m})" for b, (j, m) in buckets.items())

            if anchor_month:
                day_hits = self._collect_bucket_counts(conn, 10, target=target, prefix=f"{anchor_month}-")
                if day_hits:
                    return f"[No memory records found for {scope_label}. Active dates in {anchor_month}: {_fmt(day_hits)}.]"

            if anchor_year:
                month_hits = self._collect_bucket_counts(conn, 7, target=target, prefix=f"{anchor_year}-")
                if month_hits:
                    return f"[No memory records found for {scope_label}. Active months in {anchor_year}: {_fmt(month_hits)}.]"

            year_hits = self._collect_bucket_counts(conn, 4, target=target)
            if year_hits:
                return f"[No memory records found for {scope_label}. Active years: {_fmt(year_hits)}.]"
        finally:
            conn.close()

        return "[No memory records found matching the given criteria.]"
