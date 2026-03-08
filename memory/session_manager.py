"""
memory/session_manager.py – Session persistence for the research pipeline.

Priority:
  1. AWS DynamoDB (when credentials available)
  2. Local JSON file store (demo / offline mode)

Session lifecycle:
  create_session() → update_session() → get_session() → complete_session()
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("ai-coauthor.session")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionManager:
    """
    Manages research session state.
    Automatically falls back to local JSON files if DynamoDB is unavailable.
    """

    def __init__(self):
        self._use_dynamo = False
        self._table = None
        self._local_dir: Path = Path(__file__).parent.parent / ".sessions"
        self._local_dir.mkdir(exist_ok=True)
        self._try_init_dynamo()

    def _try_init_dynamo(self):
        try:
            from config import get_dynamodb_resource, DYNAMODB_TABLE_NAME, ensure_dynamodb_table
            # Auto-create the table if it doesn't exist yet
            ensure_dynamodb_table(DYNAMODB_TABLE_NAME)
            resource = get_dynamodb_resource()
            table = resource.Table(DYNAMODB_TABLE_NAME)
            # Test connectivity
            table.load()
            self._table = table
            self._use_dynamo = True
            logger.info("Session storage: DynamoDB (%s)", DYNAMODB_TABLE_NAME)
        except Exception as exc:
            logger.info("DynamoDB unavailable (%s) – using local JSON store", exc)
            self._use_dynamo = False


    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def create_session(
        self,
        topic: str,
        output_format: str = "IEEE",
        max_papers: int = 10,
        username: str = "anonymous",
    ) -> str:
        """Create a new session and return its session_id."""
        session_id = str(uuid.uuid4())
        session = {
            "session_id": session_id,
            "topic": topic,
            "output_format": output_format,
            "max_papers": max_papers,
            "username": username,
            "status": "created",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "agent_history": [],
            "artifacts": {},
        }
        self._save(session_id, session)
        logger.info("Session created: %s | topic=%s | user=%s", session_id, topic[:60], username)
        return session_id

    def update_session(
        self,
        session_id: str,
        status: str,
        agent_name: str = "",
        outputs: dict | None = None,
        latency_ms: int = 0,
    ):
        """Update session status and store agent outputs."""
        session = self.get_session(session_id) or {}
        session["status"] = status
        session["updated_at"] = _now_iso()

        if agent_name:
            history_entry = {
                "agent": agent_name,
                "status": status,
                "latency_ms": latency_ms,
                "timestamp": _now_iso(),
            }
            session.setdefault("agent_history", []).append(history_entry)

        if outputs:
            # Store non-object outputs only (skip RAGEngine etc.)
            serialisable = {}
            for k, v in outputs.items():
                if isinstance(v, (str, int, float, bool, list, dict, type(None))):
                    serialisable[k] = v
            session.setdefault("artifacts", {}).update(serialisable)

        self._save(session_id, session)

    def get_session(self, session_id: str) -> Optional[dict]:
        """Load a session by ID."""
        try:
            if self._use_dynamo:
                resp = self._table.get_item(Key={"session_id": session_id})
                return resp.get("Item")
            else:
                path = self._local_dir / f"{session_id}.json"
                if path.exists():
                    return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load session %s: %s", session_id, exc)
        return None

    def complete_session(self, session_id: str, metrics: dict):
        """Mark session as completed with final metrics."""
        session = self.get_session(session_id) or {}
        session["status"] = "completed"
        session["updated_at"] = _now_iso()
        session["final_metrics"] = metrics
        self._save(session_id, session)

    def list_recent_sessions(self, limit: int = 10) -> list[dict]:
        """Return up to `limit` most recent sessions (local mode only)."""
        sessions = []
        for path in sorted(self._local_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": data.get("session_id", ""),
                    "topic": data.get("topic", "")[:60],
                    "status": data.get("status", ""),
                    "created_at": data.get("created_at", ""),
                    "username": data.get("username", "anonymous"),
                })
            except Exception:
                continue
        return sessions

    def list_sessions_for_user(self, username: str, limit: int = 10) -> list[dict]:
        """Return sessions belonging to a specific user."""
        all_sessions = []
        try:
            if self._use_dynamo:
                from boto3.dynamodb.conditions import Attr
                resp = self._table.scan(
                    FilterExpression=Attr("username").eq(username),
                    ProjectionExpression="session_id, topic, #st, created_at, final_metrics",
                    ExpressionAttributeNames={"#st": "status"},
                )
                all_sessions = resp.get("Items", [])
                all_sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
            else:
                for path in sorted(self._local_dir.glob("*.json"),
                                   key=lambda p: p.stat().st_mtime, reverse=True):
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        if data.get("username", "anonymous") == username:
                            all_sessions.append({
                                "session_id": data.get("session_id", ""),
                                "topic": data.get("topic", "")[:60],
                                "status": data.get("status", ""),
                                "created_at": data.get("created_at", ""),
                            })
                    except Exception:
                        continue
        except Exception as exc:
            logger.warning("list_sessions_for_user failed: %s", exc)
        return all_sessions[:limit]

    def load_for_sharing(self, session_id: str) -> Optional[dict]:
        """
        Load a session and flatten its stored artifacts into a result dict
        that the results panel can render directly (read-only share view).
        """
        session = self.get_session(session_id)
        if not session:
            return None
        artifacts = session.get("artifacts", {})
        metrics = session.get("final_metrics", {})
        # Reconstruct a result dict mirroring what pipeline.run() returns
        result = {
            **artifacts,
            "metrics": metrics,
            "agent_errors": [],
            "topic": session.get("topic", ""),
            "_shared": True,
            "_shared_by": session.get("username", "anonymous"),
            "_shared_at": session.get("updated_at", ""),
        }
        return result

    # ──────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────

    def _save(self, session_id: str, session: dict):
        if self._use_dynamo:
            try:
                self._table.put_item(Item=_to_dynamo_safe(session))
                return
            except Exception as exc:
                logger.warning("DynamoDB save failed (%s) – falling back to local", exc)
        path = self._local_dir / f"{session_id}.json"
        # Prune non-serialisable values
        safe = _make_serialisable(session)
        path.write_text(json.dumps(safe, indent=2, default=str), encoding="utf-8")



def _to_dynamo_safe(obj: Any) -> Any:
    """Recursively convert floats→Decimal and drop None values for DynamoDB."""
    from decimal import Decimal
    if isinstance(obj, dict):
        return {k: _to_dynamo_safe(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_to_dynamo_safe(i) for i in obj]
    if isinstance(obj, float):
        return Decimal(str(obj))
    return obj


def _make_serialisable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _make_serialisable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serialisable(i) for i in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)

