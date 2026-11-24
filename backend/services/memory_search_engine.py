from datetime import datetime, timedelta
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.database import get_db_connection

STRIP_INTERNAL_TAGS_RE = re.compile(
    r"<(?:think|thought|inner_thought|monologue)\b[^>]*/>"
    r"|<(think|thought|inner_thought|monologue)\b[^>]*(?<!/)>[\s\S]*?(?:</\1>|$)"
    r"|<(property_update|finalize_mission|new_course|memory_decay|system_pass)\b[^>]*>(?:[\s\S]*?</\2>)?"
    r"|</(?:think|thought|inner_thought|monologue|property_update|finalize_mission|new_course|memory_decay|system_pass)\s*>",
    re.IGNORECASE,
)

TOOL_XML_TAGS_RE = re.compile(
    r"<tool_batch\b[^>]*/>|<tool_batch\b[^>]*(?<!/)>[\s\S]*?(?:</tool_batch>|$)"
    r"|<tool_call\b[^>]*/>|<tool_call\b[^>]*(?<!/)>[\s\S]*?(?:</tool_call>|$)"
    r"|<call_tool\b[^>]*/>|<call_tool\b[^>]*(?<!/)>[\s\S]*?(?:</call_tool>|$)"
    r"|<execute_bash\b[^>]*/>|<execute_bash\b[^>]*(?<!/)>[\s\S]*?(?:</execute_bash>|$)"
    r"|<function(?:=|\b)[^>]*/>|<function(?:=|\b)[^>]*(?<!/)>[\s\S]*?(?:</function>|$)"
    r"|</(?:tool_batch|tool_call|call_tool|execute_bash|function)\s*>",
    re.IGNORECASE,
)

DEFAULT_LIMIT = 5
MAX_LIMIT = 15
PREVIEW_CHARS = 150
DEFAULT_CONTEXT_TURNS = 4
MAX_CONTEXT_TURNS = 8
VALID_TARGETS = {"all", "journals", "conversations"}
VALID_SOURCE_TYPES = {"journal", "conversation"}
VALID_ORDERS = {"newest", "oldest"}
JOURNAL_VISIBLE_SQL = "COALESCE(status, 'active') NOT IN ('archived', 'rolled_back')"


def _normalize_stripped_whitespace(text: str) -> str:
    """Collapse trailing horizontal spaces and excessive blank lines left after tag stripping."""
    cleaned = re.sub(r"[ \t]+\n", "\n", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def strip_tool_xml_tags(text: Optional[str]) -> str:
    """Remove tool-wrapper XML tags and empty shells (e.g., <tool_batch> </tool_batch>) from text."""
    if not text:
        return ""
    return _normalize_stripped_whitespace(TOOL_XML_TAGS_RE.sub("", text))


def strip_internal_tags(text: Optional[str]) -> str:
    """Remove internal reasoning, state, and tool-wrapper tags before surfacing historical records."""
    if not text:
        return ""
    cleaned = STRIP_INTERNAL_TAGS_RE.sub("", text)
    cleaned = TOOL_XML_TAGS_RE.sub("", cleaned)
    return _normalize_stripped_whitespace(cleaned)


def format_message_for_memory(role: Optional[str], text: Optional[str]) -> str:
    """Preserve user-authored messages verbatim while stripping internal tags from assistant outputs."""
    raw = text or ""
    if (role or "").lower() == "user":
        return raw.strip()
    return strip_internal_tags(raw)


def _truncate_preview(text: str, max_chars: int = PREVIEW_CHARS) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rstrip() + "..."


def _escape_like(term: str) -> str:
    """Escape SQLite LIKE wildcards so literal '%', '_', and '\\' match verbatim."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _tokenize_search_terms(query: Optional[str]) -> List[str]:
    """Split whitespace-separated query keywords while deduplicating case-insensitively."""
    if not query or not query.strip():
        return []
    terms: List[str] = []
    seen = set()
    for raw in query.split():
        key = raw.lower()
        if key and key not in seen:
            seen.add(key)
            terms.append(raw)
    return terms


def _build_term_sql_parts(
    terms: List[str],
    col_exprs: Tuple[str, ...],
) -> Tuple[str, List[Any], str, List[Any]]:
    """Build SQL WHERE predicate and relevance match_score expression for 1+ search terms."""
    term_clauses: List[str] = []
    where_params: List[Any] = []
    for term in terms:
        pat = _escape_like(term)
        sub = " OR ".join(f"{col} LIKE ? ESCAPE '\\'" for col in col_exprs)
        term_clauses.append(f"({sub})")
        where_params.extend([pat] * len(col_exprs))

    if len(terms) == 1:
        return term_clauses[0], where_params, "1", []

    where_clause = "(" + " OR ".join(term_clauses) + ")"
    score_expr = "(" + " + ".join(f"(CASE WHEN {tc} THEN 1 ELSE 0 END)" for tc in term_clauses) + ")"
    score_params = list(where_params)
    return where_clause, where_params, score_expr, score_params


DATE_DAY_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DATE_MONTH_RE = re.compile(r"\d{4}-\d{2}")
DATE_YEAR_RE = re.compile(r"\d{4}")


def _sql_norm_ts(ts_expr: str = "timestamp") -> str:
    """Return SQL expression normalizing ISO 'T' separators to spaces."""
    return f"replace(COALESCE({ts_expr}, ''), 'T', ' ')"


def _sql_day_expr(ts_expr: str = "timestamp") -> str:
    """Return SQL expression extracting the leading YYYY-MM-DD day key."""
    return f"substr({_sql_norm_ts(ts_expr)}, 1, 10)"


def _build_date_clauses(
    date_range: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    ts_expr: str = "timestamp",
) -> Tuple[List[str], List[Any], Optional[str]]:
    """Build parameterized SQL date clauses from date_range and/or inclusive start_date/end_date."""
    norm_ts = _sql_norm_ts(ts_expr)
    day_expr = _sql_day_expr(ts_expr)
    clauses: List[str] = []
    params: List[Any] = []

    if date_range and str(date_range).strip():
        dr = str(date_range).strip().lower()
        if dr == "all":
            pass
        elif dr == "recent_7d":
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
        elif DATE_YEAR_RE.fullmatch(dr):
            clauses.append(f"{norm_ts} LIKE ?")
            params.append(f"{dr}-%")
        else:
            return [], [], (
                f"[Error] Invalid date_range '{date_range}'. "
                "Expected 'YYYY-MM-DD', 'YYYY-MM', 'YYYY', 'recent_7d', 'recent_30d', or 'all'."
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

    @staticmethod
    def _normalize_target_and_order(
        target: Optional[str],
        order: Optional[str],
    ) -> Tuple[str, str, Optional[str]]:
        """Validate and normalize target source and sort order parameters."""
        norm_target = (target or "all").strip().lower()
        if norm_target not in VALID_TARGETS:
            return "", "", f"[Error] Invalid target '{target}'. Expected one of: all, journals, conversations."
        norm_order = (order or "newest").strip().lower()
        if norm_order not in VALID_ORDERS:
            return "", "", f"[Error] Invalid order '{order}'. Expected 'newest' or 'oldest'."
        return norm_target, norm_order, None

    @staticmethod
    def _append_scope_meta(
        meta: List[str],
        date_range: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        norm_target: str,
        norm_order: str,
        always_include_target: bool = False,
        include_order: bool = True,
    ) -> None:
        """Append standardized date-scope, target, and order metadata tokens."""
        if date_range:
            meta.append(f"date_range: {date_range!r}")
        if start_date:
            meta.append(f"start_date: {start_date!r}")
        if end_date:
            meta.append(f"end_date: {end_date!r}")
        if always_include_target or norm_target != "all":
            meta.append(f"target: {norm_target}")
        if include_order and norm_order != "newest":
            meta.append(f"order: {norm_order}")

    @staticmethod
    def _build_truncation_footer(
        norm_order: str,
        summary: str,
        newest_action: str,
        oldest_action: str,
        tail_action: str,
    ) -> str:
        """Build a consistent truncation guidance footer for newest/oldest traversal."""
        action = newest_action if norm_order == "newest" else oldest_action
        return f"Note: {summary} {action} {tail_action}"

    def _collect_target_date_stats(
        self,
        conn,
        target: str,
        date_clauses: Optional[List[str]] = None,
        date_params: Optional[List[Any]] = None,
    ) -> Tuple[int, Optional[str], Optional[str]]:
        """Compute (total_rows, earliest_day, latest_day) across active records for selected target."""
        total = 0
        min_days: List[str] = []
        max_days: List[str] = []
        day_expr = _sql_day_expr()
        for key in ("journals", "conversations"):
            if target not in ("all", key):
                continue
            spec = self._TARGET_SPECS[key]
            clauses = [spec["base_where"], "length(trim(COALESCE(timestamp, ''))) >= 10"]
            params: List[Any] = []
            if date_clauses:
                clauses.extend(date_clauses)
                params.extend(date_params or [])
            row = conn.execute(
                f"SELECT COUNT(*) AS cnt, MIN({day_expr}) AS min_d, MAX({day_expr}) AS max_d "
                f"FROM {spec['table']} WHERE {' AND '.join(clauses)}",
                params,
            ).fetchone()
            if row:
                total += int(row["cnt"] or 0)
                if row["min_d"]:
                    min_days.append(row["min_d"])
                if row["max_d"]:
                    max_days.append(row["max_d"])
        return total, (min(min_days) if min_days else None), (max(max_days) if max_days else None)

    def _populate_calendar_day_map(
        self,
        conn,
        norm_target: str,
        log_date_clauses: List[str],
        log_date_params: List[Any],
        msg_date_clauses: List[str],
        msg_date_params: List[Any],
    ) -> Tuple[Dict[str, Dict[str, Any]], Optional[str]]:
        """Collect per-day journal counts and conversation session summaries from SQLite."""
        day_map: Dict[str, Dict[str, Any]] = {}

        def _ensure_day(day: str) -> Dict[str, Any]:
            if day not in day_map:
                day_map[day] = {"journals": 0, "msgs": 0, "sessions": {}}
            return day_map[day]

        if norm_target in ("all", "journals"):
            log_clauses = [
                JOURNAL_VISIBLE_SQL,
                "length(trim(COALESCE(timestamp, ''))) >= 10",
                *log_date_clauses,
            ]
            log_rows = conn.execute(
                f"""
                SELECT {_sql_day_expr()} AS day, COUNT(*) AS cnt
                FROM memory_logs
                WHERE {' AND '.join(log_clauses)}
                GROUP BY day
                """,
                log_date_params,
            ).fetchall()
            for row in log_rows:
                if row["day"]:
                    _ensure_day(row["day"])["journals"] = row["cnt"]

        if norm_target in ("all", "conversations"):
            msg_clauses = [
                "m.role IN ('user', 'assistant')",
                "length(trim(COALESCE(m.timestamp, ''))) >= 10",
                *msg_date_clauses,
            ]
            msg_rows = conn.execute(
                f"""
                SELECT
                    {_sql_day_expr('m.timestamp')} AS day,
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

        _, db_earliest, _ = self._collect_target_date_stats(conn, norm_target)
        return day_map, db_earliest

    @staticmethod
    def _format_calendar_day_line(day: str, entry: Dict[str, Any], norm_target: str) -> str:
        """Format one daily overview bullet line for the calendar view."""
        j_cnt = entry["journals"]
        if norm_target == "journals":
            return f"- [{day}] {j_cnt} journal{'s' if j_cnt != 1 else ''}"

        sess_cnt = len(entry["sessions"])
        msg_cnt = entry["msgs"]
        parts = [
            f"{sess_cnt} session{'s' if sess_cnt != 1 else ''}",
            f"{msg_cnt} msg{'s' if msg_cnt != 1 else ''}",
        ]
        if norm_target == "all":
            parts.append(f"{j_cnt} journal{'s' if j_cnt != 1 else ''}")

        titles = list(entry["sessions"].values())[:4]
        title_part = f" | topics: {', '.join(repr(t) for t in titles)}" if titles else ""
        if sess_cnt > 4:
            title_part += f" (+{sess_cnt - 4} more)"
        return f"- [{day}] {', '.join(parts)}{title_part}"

    def calendar(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        date_range: Optional[str] = None,
        target: str = "all",
        order: str = "newest",
        limit: Optional[int] = None,
    ) -> str:
        """Aggregate per-day conversation session counts, session titles, and diary counts."""
        norm_target, norm_order, arg_err = self._normalize_target_and_order(target, order)
        if arg_err:
            return arg_err

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

        conn = get_db_connection()
        try:
            day_map, db_earliest = self._populate_calendar_day_map(
                conn,
                norm_target,
                log_date_clauses,
                log_date_params,
                msg_date_clauses,
                msg_date_params,
            )
        finally:
            conn.close()

        if not day_map:
            return self._build_empty_notice(
                date_range=date_range,
                start_date=start_date,
                end_date=end_date,
                target=norm_target,
            )

        all_days = sorted(day_map.keys())
        total_days = len(all_days)
        scope_earliest, scope_latest = all_days[0], all_days[-1]
        is_truncated = total_days > capped_days
        selected_days = all_days[:capped_days] if norm_order == "oldest" else all_days[-capped_days:]
        lines = [self._format_calendar_day_line(day, day_map[day], norm_target) for day in selected_days]

        meta: List[str] = []
        self._append_scope_meta(meta, date_range, start_date, end_date, norm_target, norm_order)

        if is_truncated:
            effective_earliest = db_earliest or scope_earliest
            showing_word = "oldest" if norm_order == "oldest" else "latest"
            meta.append(f"earliest_active_day: {effective_earliest}")
            meta.append(f"total_active_days: {total_days} (showing {showing_word} {len(selected_days)})")
            footer = self._build_truncation_footer(
                norm_order=norm_order,
                summary=(
                    f"Truncated — showing {showing_word} {len(selected_days)} of {total_days} active days in range "
                    f"({scope_earliest}..{scope_latest}); earliest active day in DB for target={norm_target!r} is "
                    f"{effective_earliest}."
                ),
                newest_action=(
                    f'Call get_memory_calendar(order="oldest") to start from {scope_earliest}, '
                    "or narrow start_date/end_date. Call"
                ),
                oldest_action=f"Narrow start_date/end_date to step past {selected_days[-1]}, or call",
                tail_action='get_memory_timeline with date_range="YYYY-MM-DD" to inspect records for a specific day.',
            )
        else:
            meta.append(f"active_days: {len(selected_days)}")
            footer = 'Note: Call get_memory_timeline with date_range="YYYY-MM-DD" to inspect records for a specific day.'

        header = f"[Memory Calendar Overview | {' | '.join(meta)}]"
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
                    f"""
                    SELECT id, timestamp, level, summary, content, session_id
                    FROM memory_logs
                    WHERE id = ? AND {JOURNAL_VISIBLE_SQL}
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
                clean = format_message_for_memory(row["role"], row["content"])
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
        order: str = "newest",
    ) -> str:
        return self._run_preview_query(
            mode="timeline",
            query=query,
            target=target,
            date_range=date_range,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            order=order,
        )

    _TARGET_SPECS = {
        "journals": {
            "table": "memory_logs",
            "base_where": JOURNAL_VISIBLE_SQL,
            "select_cols": "id, timestamp, summary, content",
            "search_cols": ("COALESCE(summary, '')", "COALESCE(content, '')"),
            "type_rank": 1,
        },
        "conversations": {
            "table": "chat_messages",
            "base_where": "role IN ('user', 'assistant')",
            "select_cols": "id, session_id, role, content, timestamp",
            "search_cols": ("COALESCE(content, '')",),
            "type_rank": 0,
        },
    }

    @staticmethod
    def _format_bucket_counts(buckets: Dict[str, Tuple[int, int]]) -> str:
        """Format date-bucket count pairs into a compact summary string."""
        return ", ".join(f"{b} ({j + m})" for b, (j, m) in buckets.items())

    def _fetch_target_hits(
        self,
        conn,
        target_key: str,
        terms: List[str],
        full_query: str,
        date_clauses: List[str],
        date_params: List[Any],
        fetch_limit: Optional[int] = None,
        order: str = "newest",
    ) -> List[Tuple[int, int, str, int, int, str]]:
        """Query a single memory source, strip internal tags, score term matches, and format preview hits."""
        spec = self._TARGET_SPECS[target_key]
        clauses = [spec["base_where"], *date_clauses]
        sql_params = list(date_params)
        score_expr = "1"
        score_params: List[Any] = []
        if terms:
            kw_where, kw_params, score_expr, score_params = _build_term_sql_parts(terms, spec["search_cols"])
            clauses.append(kw_where)
            sql_params.extend(kw_params)

        norm_ts_sql = _sql_norm_ts()
        if terms:
            order_by = f"match_score DESC, {norm_ts_sql} DESC, id DESC" if len(terms) >= 2 else f"{norm_ts_sql} DESC, id DESC"
        else:
            order_by = f"{norm_ts_sql} ASC, id ASC" if order == "oldest" else f"{norm_ts_sql} DESC, id DESC"
        limit_sql = "LIMIT ?" if fetch_limit is not None else ""
        query_params: List[Any] = [*score_params, *sql_params]
        if fetch_limit is not None:
            query_params.append(fetch_limit)

        rows = conn.execute(
            f"""
            SELECT {spec['select_cols']}, {score_expr} AS match_score
            FROM {spec['table']}
            WHERE {' AND '.join(clauses)}
            ORDER BY {order_by}
            {limit_sql}
            """,
            query_params,
        ).fetchall()

        query_lower = full_query.lower()
        hits: List[Tuple[int, int, str, int, int, str]] = []
        for row in rows:
            if target_key == "journals":
                preview = strip_internal_tags(row["summary"] or row["content"])
                if not preview:
                    continue
                searchable = "\n".join(
                    p for p in (strip_internal_tags(row["summary"]), strip_internal_tags(row["content"])) if p
                ).lower()
                line = f"- [journal #{row['id']} | {row['timestamp']}] {_truncate_preview(preview)}"
            else:
                preview = format_message_for_memory(row["role"], row["content"])
                if not preview:
                    continue
                searchable = preview.lower()
                line = (
                    f"- [conversation #{row['id']} | session:{row['session_id']} | "
                    f"{row['timestamp']} | {row['role']}] {_truncate_preview(preview)}"
                )

            hit_count = sum(1 for t in terms if t.lower() in searchable) if terms else 1
            if terms and hit_count == 0:
                continue
            exact_hit = 1 if (query_lower and query_lower in searchable) else 0
            norm_ts = str(row["timestamp"] or "").replace("T", " ")
            hits.append((hit_count, exact_hit, norm_ts, spec["type_rank"], row["id"], line))
        return hits

    def _query_timeline_lines(
        self,
        conn,
        norm_target: str,
        date_clauses: List[str],
        date_params: List[Any],
        capped_limit: int,
        norm_order: str,
    ) -> Tuple[List[str], int, Optional[str], Optional[str], Optional[str]]:
        """Run chronological timeline preview across active targets and return pagination anchors."""
        timeline_hits: List[Tuple[int, int, str, int, int, str]] = []
        for key in ("journals", "conversations"):
            if norm_target in ("all", key):
                timeline_hits.extend(
                    self._fetch_target_hits(
                        conn,
                        key,
                        [],
                        "",
                        date_clauses,
                        date_params,
                        fetch_limit=capped_limit + 1,
                        order=norm_order,
                    )
                )
        timeline_hits.sort(
            key=lambda item: (item[2], item[3], item[4]),
            reverse=(norm_order != "oldest"),
        )
        lines = [item[-1] for item in timeline_hits[:capped_limit]]
        if not lines:
            return [], 0, None, None, None

        total_matching, scope_min_day, scope_max_day = self._collect_target_date_stats(
            conn, norm_target, date_clauses, date_params
        )
        total_matching = max(total_matching, len(timeline_hits))
        _, db_earliest, _ = self._collect_target_date_stats(conn, norm_target)
        return lines, total_matching, scope_min_day, scope_max_day, db_earliest

    def _query_search_lines(
        self,
        conn,
        norm_target: str,
        query: str,
        terms: List[str],
        date_clauses: List[str],
        date_params: List[Any],
        capped_limit: int,
    ) -> List[str]:
        """Run single-term or multi-term keyword search across active targets."""
        multi_term = len(terms) >= 2
        lines: List[str] = []
        ranked_hits: List[Tuple[int, int, str, int, int, str]] = []

        for key in ("journals", "conversations"):
            if norm_target not in ("all", key):
                continue
            remaining = capped_limit if multi_term else (capped_limit - len(lines))
            if remaining <= 0:
                continue
            hits = self._fetch_target_hits(
                conn,
                key,
                terms,
                query,
                date_clauses,
                date_params,
                fetch_limit=max(remaining * 4, 40),
            )
            if multi_term:
                ranked_hits.extend(hits)
            else:
                lines.extend(item[-1] for item in hits[:remaining])

        if multi_term:
            ranked_hits.sort(reverse=True)
            return [item[-1] for item in ranked_hits[:capped_limit]]
        return lines

    def _run_preview_query(
        self,
        mode: str,
        query: str,
        target: str,
        date_range: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        limit: Optional[int],
        order: str = "newest",
    ) -> str:
        """Execute timeline or keyword search preview and wrap hits with navigation metadata."""
        norm_target, norm_order, arg_err = self._normalize_target_and_order(target, order)
        if arg_err:
            return arg_err

        date_clauses, date_params, date_err = _build_date_clauses(
            date_range=date_range,
            start_date=start_date,
            end_date=end_date,
        )
        if date_err:
            return date_err

        capped_limit = self._normalize_limit(limit)
        terms = _tokenize_search_terms(query)
        total_matching = 0
        scope_min_day: Optional[str] = None
        scope_max_day: Optional[str] = None
        db_earliest: Optional[str] = None

        conn = get_db_connection()
        try:
            if not terms:
                lines, total_matching, scope_min_day, scope_max_day, db_earliest = self._query_timeline_lines(
                    conn, norm_target, date_clauses, date_params, capped_limit, norm_order
                )
            else:
                lines = self._query_search_lines(
                    conn, norm_target, query, terms, date_clauses, date_params, capped_limit
                )
        finally:
            conn.close()

        if not lines:
            return self._build_empty_notice(
                date_range=date_range,
                start_date=start_date,
                end_date=end_date,
                target=norm_target,
                query=query,
            )

        meta = [f"mode: {mode}"]
        if query:
            meta.append(f"query: {query!r}")
        self._append_scope_meta(
            meta,
            date_range,
            start_date,
            end_date,
            norm_target,
            norm_order,
            always_include_target=True,
            include_order=not terms,
        )
        meta.append(f"hits: {len(lines)}")

        footer = "Note: Call expand_memory with source_type and record_id to inspect full details if needed."
        if not terms and total_matching > len(lines):
            effective_earliest = db_earliest or scope_min_day
            meta.append(f"total_matching: {total_matching}")
            if effective_earliest:
                meta.append(f"earliest_active_day: {effective_earliest}")
            span_label = f"{scope_min_day}..{scope_max_day}" if (scope_min_day and scope_max_day) else "scope"
            showing_word = "oldest" if norm_order == "oldest" else "newest"
            footer = self._build_truncation_footer(
                norm_order=norm_order,
                summary=(
                    f"Showing {showing_word} {len(lines)} of {total_matching} records ({span_label}); "
                    f'earliest_active_day={effective_earliest or "unknown"}.'
                ),
                newest_action=f'Call get_memory_timeline(order="oldest") to read from {scope_min_day or "the start"}, or',
                oldest_action="Narrow start_date/end_date to step forward, or",
                tail_action="call expand_memory with source_type and record_id to inspect full details.",
            )

        header = f"[Memory Search Results | {' | '.join(meta)}]"
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
        norm_ts = _sql_norm_ts()
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
            _query_table("memory_logs", JOURNAL_VISIBLE_SQL, 0)
        if target in ("all", "conversations"):
            _query_table("chat_messages", "role IN ('user', 'assistant')", 1)

        return {k: (v[0], v[1]) for k, v in sorted(counts.items())}

    def _build_peer_target_hint(
        self,
        conn,
        target: str,
        date_range: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        scope_label: Optional[str],
        query: str,
        anchor_year: Optional[str],
    ) -> str:
        """Build an objective hint if the peer target ('journals' vs 'conversations') holds matching records."""
        if target not in ("journals", "conversations"):
            return ""
        peer_target = "journals" if target == "conversations" else "conversations"
        date_clauses, date_params, date_err = _build_date_clauses(
            date_range=date_range,
            start_date=start_date,
            end_date=end_date,
        )
        if date_err:
            return ""

        terms = _tokenize_search_terms(query)
        peer_count = len(self._fetch_target_hits(conn, peer_target, terms, query, date_clauses, date_params))
        if peer_count > 0:
            scope_phrase = f" for {scope_label}" if scope_label else ""
            return (
                f" Note: {peer_count} matching {peer_target} record(s) exist{scope_phrase}"
                f" — retry with target='all' or target='{peer_target}'."
            )

        if scope_label and not terms:
            peer_buckets = (
                self._collect_bucket_counts(conn, 7, target=peer_target, prefix=f"{anchor_year}-")
                if anchor_year
                else {}
            )
            if not peer_buckets:
                peer_buckets = self._collect_bucket_counts(conn, 4, target=peer_target)
            if peer_buckets:
                return (
                    f" Note: {peer_target} has active records ({self._format_bucket_counts(peer_buckets)})"
                    f" — consider target='all' or target='{peer_target}'."
                )
        return ""

    @staticmethod
    def _resolve_empty_scope_anchors(
        date_range: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract display scope label plus month/year fallback anchors from date filters."""
        dr = str(date_range).strip() if date_range and str(date_range).strip() else None
        sd = str(start_date).strip() if start_date and str(start_date).strip() else None
        ed = str(end_date).strip() if end_date and str(end_date).strip() else None
        if dr and dr.lower() == "all" and not sd and not ed:
            scope_label = None
        else:
            scope_label = (dr or f"{sd or '...'}..{ed or '...'}") if (dr or sd or ed) else None

        anchor_month: Optional[str] = None
        anchor_year: Optional[str] = None
        if dr and DATE_DAY_RE.fullmatch(dr):
            anchor_month, anchor_year = dr[:7], dr[:4]
        elif dr and DATE_MONTH_RE.fullmatch(dr):
            anchor_year = dr[:4]
        elif dr and DATE_YEAR_RE.fullmatch(dr):
            anchor_year = dr
        elif sd and ed and sd[:7] == ed[:7]:
            anchor_month, anchor_year = sd[:7], sd[:4]
        elif sd or ed:
            anchor_year = (sd or ed)[:4]
        elif dr and dr.lower() in ("recent_7d", "recent_30d"):
            now = datetime.now()
            anchor_month, anchor_year = now.strftime("%Y-%m"), now.strftime("%Y")

        return scope_label, anchor_month, anchor_year

    def _find_active_buckets_hint(
        self,
        conn,
        target: str,
        anchor_month: Optional[str],
        anchor_year: Optional[str],
    ) -> str:
        """Find nearest populated day/month/year bucket counts for progressive empty-date guidance."""
        candidates: List[Tuple[int, Optional[str], str]] = []
        if anchor_month:
            candidates.append((10, f"{anchor_month}-", f"Active dates in {anchor_month}"))
        if anchor_year:
            candidates.append((7, f"{anchor_year}-", f"Active months in {anchor_year}"))
        candidates.append((4, None, "Active years"))

        for bucket_len, prefix, label in candidates:
            hits = self._collect_bucket_counts(conn, bucket_len, target=target, prefix=prefix)
            if hits:
                return f"{label}: {self._format_bucket_counts(hits)}."
        return ""

    def _build_empty_notice(
        self,
        date_range: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        target: str = "all",
        query: str = "",
    ) -> str:
        """Build an objective empty notice with progressive active hints and cross-target guidance."""
        scope_label, anchor_month, anchor_year = self._resolve_empty_scope_anchors(
            date_range, start_date, end_date
        )

        conn = get_db_connection()
        try:
            peer_hint = self._build_peer_target_hint(
                conn=conn,
                target=target,
                date_range=date_range,
                start_date=start_date,
                end_date=end_date,
                scope_label=scope_label,
                query=query,
                anchor_year=anchor_year,
            )

            if not scope_label:
                if peer_hint:
                    return f"[No memory records found matching the given criteria (target='{target}').{peer_hint}]"
                return "[No memory records found matching the given criteria.]"

            active_hint = self._find_active_buckets_hint(conn, target, anchor_month, anchor_year)
            if active_hint or peer_hint:
                target_note = "" if target == "all" else f" (target='{target}')"
                parts = [f"No memory records found for {scope_label}{target_note}."]
                if active_hint:
                    parts.append(active_hint)
                if peer_hint:
                    parts.append(peer_hint.strip())
                return f"[{' '.join(parts)}]"
        finally:
            conn.close()

        return "[No memory records found matching the given criteria.]"
