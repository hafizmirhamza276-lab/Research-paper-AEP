"""The ground-truth applied-mutation ledger (PAPER_ROADMAP.md section 3.1(1)).

This is the oracle. It answers one question the system under test is not
allowed to answer about itself: *how many times did the external world
actually change?* Every duplicate rate in the paper is derived from these
rows, so the ledger is held to the same standard as the protocol it measures.

Three properties, each pinned by test in ``tests/test_ledger.py``:

**Atomicity.** :meth:`GroundTruthLedger.record_applied_mutation` performs the
simulated state change and writes the ledger row inside a single
``BEGIN IMMEDIATE ... COMMIT``. There is no interleaving in which the external
world has changed but the oracle does not know, or the reverse. The service
must never write one without the other, and cannot: they are the same call.

**Durability.** ``journal_mode=WAL`` plus ``synchronous=FULL``. WAL means a
killed process leaves a consistent database with no journal to replay; FULL
means a committed row has reached stable storage before the commit returns.
The crash model actually injected -- SIGKILL of the service -- would be
covered by ``NORMAL``; FULL costs one fsync per applied mutation and removes
the qualification from the claim.

**Isolation.** One connection *per thread*, not one connection shared between
them. The service answers read-backs and oracle queries from a thread pool
while mutations are being applied, and a ``SELECT`` issued on the same
connection as an open ``BEGIN IMMEDIATE`` interleaves with that transaction.
Phase 2B Session 2's self-validation run observed all three consequences: a
committed row reported absent, one application reported as a ``CONFLICT``, and
raw ``sqlite3`` errors. Each of those corrupts a number the paper reports and
none is a property of the system under test. WAL exists precisely so that
readers on their own connections take a consistent snapshot while a writer
holds the write lock, so that is what this does; writes remain serialised by
:attr:`GroundTruthLedger._write_lock` because the effect count is a
read-modify-write. Pinned by ``tests/test_ledger_concurrency.py``.

**Classification, not counting.** :meth:`duplicate_groups` distinguishes two
things a naive ``GROUP BY`` would merge (Definition 3 below).

    **Definition 3 (duplicate classes).** Let ``G`` be the set of applied
    mutations sharing one fingerprint ``F`` (Definition 1 in
    ``fingerprint.py``), with ``|G| > 1``.

    * ``G`` is an **EXACT_DUPLICATE** iff every member has the same payload
      digest ``D``: the same mutation, byte-identical, applied ``|G|`` times.
      The external world changed ``|G| - 1`` times more than the caller
      intended.
    * ``G`` is a **FINGERPRINT_CONFLICT** iff its members carry two or more
      distinct payload digests: requests that denote the same mutation but do
      not agree on their non-identifying content. This is reported separately
      because it indicates a defect in the caller or in the endpoint's
      declared identity fields, not merely a retry that got through.

    Groups of size 1 are not duplicates and are not reported. The headline
    count is ``sum(|G| - 1)`` over all reported groups
    (:meth:`duplicate_application_count`), because the metric is *extra
    applications*, not *affected mutations*.

The ledger never stores request payloads or protected material -- only
digests (see ``fingerprint.redact_envelope``), so the database can be
published as part of the artifact.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

#: Written into ``ledger_meta``. Bumping it is a statement that previously
#: collected result databases are not comparable to new ones.
LEDGER_SCHEMA_VERSION = "aep.mock-legacy-api.ledger/1"

#: Digests are lower-case hex SHA-256. Enforced rather than assumed: a mixed
#: case digest would silently form its own duplicate group.
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")

#: Separates endpoint from target in the simulated-state primary key. A unit
#: separator cannot occur in either, so the key is unambiguous.
_RESOURCE_KEY_SEPARATOR = "\x1f"

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS ledger_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS applied_mutations (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id            TEXT NOT NULL UNIQUE,
        endpoint           TEXT NOT NULL,
        target             TEXT NOT NULL,
        fingerprint        TEXT NOT NULL,
        payload_digest     TEXT NOT NULL,
        client_reference   TEXT,
        response_class     TEXT NOT NULL,
        delivery_index     INTEGER NOT NULL,
        applied_at_ms      INTEGER NOT NULL,
        external_reference TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS simulated_state (
        resource_key  TEXT PRIMARY KEY,
        endpoint      TEXT NOT NULL,
        target        TEXT NOT NULL,
        effect_count  INTEGER NOT NULL,
        last_call_id  TEXT NOT NULL,
        updated_at_ms INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_applied_fingerprint "
    "ON applied_mutations (fingerprint)",
    "CREATE INDEX IF NOT EXISTS ix_applied_client_reference "
    "ON applied_mutations (client_reference)",
    "CREATE INDEX IF NOT EXISTS ix_applied_resource "
    "ON applied_mutations (endpoint, target)",
)


class LedgerError(Exception):
    """A row was refused because the oracle could not interpret it."""


class DuplicateClass(str, Enum):
    """See Definition 3 in the module docstring."""

    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    FINGERPRINT_CONFLICT = "FINGERPRINT_CONFLICT"


@dataclass(frozen=True)
class AppliedMutation:
    """One mutation that actually changed the simulated external world."""

    id: int
    call_id: str
    endpoint: str
    target: str
    fingerprint: str
    payload_digest: str
    client_reference: str | None
    response_class: str
    delivery_index: int
    applied_at_ms: int
    external_reference: str


@dataclass(frozen=True)
class SimulatedResource:
    """The simulated external state the ledger is the record of."""

    endpoint: str
    target: str
    effect_count: int
    last_call_id: str
    updated_at_ms: int


@dataclass(frozen=True)
class DuplicateGroup:
    """One set of applied mutations sharing a fingerprint."""

    fingerprint: str
    endpoint: str
    duplicate_class: DuplicateClass
    applications: int
    distinct_payloads: int
    call_ids: tuple[str, ...]

    @property
    def duplicate_applications(self) -> int:
        """Applications beyond the one the caller intended."""
        return self.applications - 1


@dataclass(frozen=True)
class ConsistencyReport:
    """Does the ledger explain the simulated state, exactly?"""

    applied_rows: int
    total_effect_count: int
    disagreeing_resources: tuple[tuple[str, str, int, int], ...]

    @property
    def is_consistent(self) -> bool:
        return (
            self.applied_rows == self.total_effect_count
            and not self.disagreeing_resources
        )


def _require_digest(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA256_HEX.fullmatch(value) is None:
        raise LedgerError(
            f"{field} must be a lower-case hex SHA-256 digest, got {value!r}"
        )
    return value


def _require_identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise LedgerError(f"{field} must be a non-empty string under 512 chars")
    return value


class GroundTruthLedger:
    """Durable record of every mutation the mock API actually applied."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._initialised = False
        # One connection per thread (see "Isolation" in the module docstring).
        self._local = threading.local()
        # Every live connection, so close() can release them all rather than
        # leaking one file handle per service worker thread.
        self._connections: list[sqlite3.Connection] = []
        self._connections_lock = threading.Lock()
        # Writes are serialised here rather than relying on SQLite's busy
        # handling, which would surface as a retry rather than as the ordering
        # the oracle needs. Still required with per-thread connections: the
        # effect count is a read-modify-write.
        self._write_lock = threading.Lock()

    # -- lifecycle ---------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open and configure one connection for the calling thread.

        ``synchronous`` and ``busy_timeout`` are per-connection settings, so a
        connection that skipped them would quietly weaken the durability claim
        for every write made on it. ``journal_mode`` is a property of the
        database file, but is asserted on each connection because a database
        that is not in WAL cannot support this access pattern at all.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None disables the driver's implicit transaction
        # handling so that BEGIN IMMEDIATE / COMMIT below are exactly the
        # transaction boundaries, with nothing inserted around them.
        connection = sqlite3.connect(
            self.path, isolation_level=None, check_same_thread=False
        )
        connection.row_factory = sqlite3.Row
        mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        if str(mode).lower() != "wal":
            connection.close()
            raise LedgerError(
                f"ledger requires WAL journal mode, the database reports {mode!r}"
            )
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        with self._connections_lock:
            self._connections.append(connection)
        return connection

    def initialise(self) -> None:
        """Open (creating if needed) and assert the durability settings.

        Safe to call repeatedly: every statement is ``IF NOT EXISTS`` and the
        meta row is written with ``INSERT OR IGNORE``.
        """
        connection = self._thread_connection(create=True)
        for statement in _SCHEMA:
            connection.execute(statement)
        connection.execute(
            "INSERT OR IGNORE INTO ledger_meta (key, value) VALUES (?, ?)",
            ("schema_version", LEDGER_SCHEMA_VERSION),
        )
        self._initialised = True

    def close(self) -> None:
        with self._connections_lock:
            connections, self._connections = self._connections, []
        for connection in connections:
            connection.close()
        self._local = threading.local()
        self._initialised = False

    def open_connection_count(self) -> int:
        """How many connections are currently open. Asserted by test."""
        with self._connections_lock:
            return len(self._connections)

    def _thread_connection(self, *, create: bool = False) -> sqlite3.Connection:
        connection = getattr(self._local, "connection", None)
        if connection is None:
            if not create and not self._initialised:
                raise LedgerError("ledger is not initialised")
            connection = self._connect()
            self._local.connection = connection
        return connection

    def _require_connection(self) -> sqlite3.Connection:
        return self._thread_connection()

    # -- declared settings, asserted by test -------------------------------

    def journal_mode(self) -> str:
        return str(
            self._require_connection().execute("PRAGMA journal_mode").fetchone()[0]
        ).lower()

    def synchronous(self) -> str:
        value = int(
            self._require_connection().execute("PRAGMA synchronous").fetchone()[0]
        )
        return {0: "OFF", 1: "NORMAL", 2: "FULL", 3: "EXTRA"}.get(value, str(value))

    def schema_version(self) -> str:
        row = self._require_connection().execute(
            "SELECT value FROM ledger_meta WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            raise LedgerError("ledger has no recorded schema version")
        return str(row["value"])

    # -- the write path ----------------------------------------------------

    def record_applied_mutation(
        self,
        *,
        call_id: str,
        endpoint: str,
        target: str,
        fingerprint: str,
        payload_digest: str,
        client_reference: str | None,
        response_class: str,
        delivery_index: int,
        applied_at_ms: int,
        before_commit: Callable[[], None] | None = None,
        after_commit: Callable[[], None] | None = None,
    ) -> AppliedMutation:
        """Apply one mutation to the simulated world and record it, atomically.

        ``before_commit`` runs inside the open transaction, ``after_commit``
        immediately after it. Both exist so crash injection can be aimed at
        either side of the commit boundary without the crash logic knowing
        anything about SQL; in normal operation both are ``None``.
        """
        _require_identifier(call_id, "call_id")
        _require_identifier(endpoint, "endpoint")
        _require_identifier(target, "target")
        _require_identifier(response_class, "response_class")
        _require_digest(fingerprint, "fingerprint")
        _require_digest(payload_digest, "payload_digest")
        if client_reference is not None:
            _require_identifier(client_reference, "client_reference")
        if not isinstance(delivery_index, int) or delivery_index < 1:
            raise LedgerError("delivery_index must be a positive integer")
        if not isinstance(applied_at_ms, int):
            raise LedgerError("applied_at_ms must be an integer")

        connection = self._require_connection()
        resource_key = f"{endpoint}{_RESOURCE_KEY_SEPARATOR}{target}"
        external_reference = f"mock-effect-{call_id}"

        # BEGIN IMMEDIATE takes the write lock now rather than on first write,
        # so two concurrent applications cannot both read the current effect
        # count and then both write it back.
        with self._write_lock:
            cursor = self._apply(
                connection,
                resource_key=resource_key,
                endpoint=endpoint,
                target=target,
                call_id=call_id,
                fingerprint=fingerprint,
                payload_digest=payload_digest,
                client_reference=client_reference,
                response_class=response_class,
                delivery_index=delivery_index,
                applied_at_ms=applied_at_ms,
                external_reference=external_reference,
                before_commit=before_commit,
            )

        if after_commit is not None:
            after_commit()

        return AppliedMutation(
            id=int(cursor.lastrowid or 0),
            call_id=call_id,
            endpoint=endpoint,
            target=target,
            fingerprint=fingerprint,
            payload_digest=payload_digest,
            client_reference=client_reference,
            response_class=response_class,
            delivery_index=delivery_index,
            applied_at_ms=applied_at_ms,
            external_reference=external_reference,
        )

    @staticmethod
    def _apply(
        connection: sqlite3.Connection,
        *,
        resource_key: str,
        endpoint: str,
        target: str,
        call_id: str,
        fingerprint: str,
        payload_digest: str,
        client_reference: str | None,
        response_class: str,
        delivery_index: int,
        applied_at_ms: int,
        external_reference: str,
        before_commit: Callable[[], None] | None,
    ) -> sqlite3.Cursor:
        """The one transaction. Both writes commit together or neither does."""
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                """
                INSERT INTO simulated_state (
                    resource_key, endpoint, target, effect_count,
                    last_call_id, updated_at_ms
                ) VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT (resource_key) DO UPDATE SET
                    effect_count  = effect_count + 1,
                    last_call_id  = excluded.last_call_id,
                    updated_at_ms = excluded.updated_at_ms
                """,
                (resource_key, endpoint, target, call_id, applied_at_ms),
            )
            cursor = connection.execute(
                """
                INSERT INTO applied_mutations (
                    call_id, endpoint, target, fingerprint, payload_digest,
                    client_reference, response_class, delivery_index,
                    applied_at_ms, external_reference
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    call_id,
                    endpoint,
                    target,
                    fingerprint,
                    payload_digest,
                    client_reference,
                    response_class,
                    delivery_index,
                    applied_at_ms,
                    external_reference,
                ),
            )
            if before_commit is not None:
                before_commit()
            connection.execute("COMMIT")
        except BaseException:
            # Includes the injected crash: a process that dies here has never
            # committed, so neither the effect nor its record exists.
            connection.execute("ROLLBACK")
            raise
        return cursor

    # -- the read paths ----------------------------------------------------

    def _mutations(self, where: str = "", parameters: tuple = ()) -> tuple[
        AppliedMutation, ...
    ]:
        rows = self._require_connection().execute(
            "SELECT id, call_id, endpoint, target, fingerprint, payload_digest, "
            "client_reference, response_class, delivery_index, applied_at_ms, "
            f"external_reference FROM applied_mutations {where} ORDER BY id",
            parameters,
        ).fetchall()
        return tuple(
            AppliedMutation(
                id=int(row["id"]),
                call_id=row["call_id"],
                endpoint=row["endpoint"],
                target=row["target"],
                fingerprint=row["fingerprint"],
                payload_digest=row["payload_digest"],
                client_reference=row["client_reference"],
                response_class=row["response_class"],
                delivery_index=int(row["delivery_index"]),
                applied_at_ms=int(row["applied_at_ms"]),
                external_reference=row["external_reference"],
            )
            for row in rows
        )

    def applied_mutations(self) -> tuple[AppliedMutation, ...]:
        return self._mutations()

    def applications_for_fingerprint(
        self, fingerprint: str
    ) -> tuple[AppliedMutation, ...]:
        return self._mutations("WHERE fingerprint = ?", (fingerprint,))

    def applications_for_client_reference(
        self, client_reference: str
    ) -> tuple[AppliedMutation, ...]:
        return self._mutations("WHERE client_reference = ?", (client_reference,))

    def applications_for_resource(
        self, *, endpoint: str, target: str
    ) -> tuple[AppliedMutation, ...]:
        return self._mutations(
            "WHERE endpoint = ? AND target = ?", (endpoint, target)
        )

    def simulated_state(self) -> tuple[SimulatedResource, ...]:
        rows = self._require_connection().execute(
            "SELECT endpoint, target, effect_count, last_call_id, updated_at_ms "
            "FROM simulated_state ORDER BY resource_key"
        ).fetchall()
        return tuple(
            SimulatedResource(
                endpoint=row["endpoint"],
                target=row["target"],
                effect_count=int(row["effect_count"]),
                last_call_id=row["last_call_id"],
                updated_at_ms=int(row["updated_at_ms"]),
            )
            for row in rows
        )

    def duplicate_groups(self) -> tuple[DuplicateGroup, ...]:
        """Definition 3, as one query plus an explicit classification."""
        rows = self._require_connection().execute(
            """
            SELECT fingerprint,
                   MIN(endpoint)                  AS endpoint,
                   COUNT(*)                       AS applications,
                   COUNT(DISTINCT payload_digest) AS distinct_payloads,
                   GROUP_CONCAT(call_id, char(31)) AS call_ids
            FROM applied_mutations
            GROUP BY fingerprint
            HAVING COUNT(*) > 1
            ORDER BY fingerprint
            """
        ).fetchall()
        return tuple(
            DuplicateGroup(
                fingerprint=row["fingerprint"],
                endpoint=row["endpoint"],
                duplicate_class=(
                    DuplicateClass.EXACT_DUPLICATE
                    if int(row["distinct_payloads"]) == 1
                    else DuplicateClass.FINGERPRINT_CONFLICT
                ),
                applications=int(row["applications"]),
                distinct_payloads=int(row["distinct_payloads"]),
                call_ids=tuple(str(row["call_ids"]).split(_RESOURCE_KEY_SEPARATOR)),
            )
            for row in rows
        )

    def duplicate_application_count(self) -> int:
        """``sum(|G| - 1)``: applications the external world did not need."""
        return sum(group.duplicate_applications for group in self.duplicate_groups())

    def consistency_report(self) -> ConsistencyReport:
        """Does every simulated effect have exactly one ledger row?

        This is the invariant the SIGKILL recovery test asserts. It can only
        be violated by a non-atomic write path, which is why it is checked
        rather than assumed.
        """
        connection = self._require_connection()
        # Three queries that must describe one instant. Without an explicit
        # read transaction a mutation committing between them makes the
        # ledger report itself inconsistent when it is not -- a false alarm
        # on the one invariant the SIGKILL recovery test asserts. WAL gives a
        # deferred transaction a stable snapshot without blocking the writer.
        connection.execute("BEGIN DEFERRED")
        try:
            report = self._consistency_within_snapshot(connection)
        finally:
            connection.execute("COMMIT")
        return report

    @staticmethod
    def _consistency_within_snapshot(
        connection: sqlite3.Connection,
    ) -> ConsistencyReport:
        applied_rows = int(
            connection.execute("SELECT COUNT(*) FROM applied_mutations").fetchone()[0]
        )
        total_effect_count = int(
            connection.execute(
                "SELECT COALESCE(SUM(effect_count), 0) FROM simulated_state"
            ).fetchone()[0]
        )
        disagreeing = connection.execute(
            """
            SELECT state.endpoint            AS endpoint,
                   state.target              AS target,
                   state.effect_count        AS effect_count,
                   COALESCE(counted.rows, 0) AS ledger_rows
            FROM simulated_state AS state
            LEFT JOIN (
                SELECT endpoint, target, COUNT(*) AS rows
                FROM applied_mutations
                GROUP BY endpoint, target
            ) AS counted
              ON counted.endpoint = state.endpoint
             AND counted.target = state.target
            WHERE state.effect_count != COALESCE(counted.rows, 0)
            ORDER BY state.endpoint, state.target
            """
        ).fetchall()
        return ConsistencyReport(
            applied_rows=applied_rows,
            total_effect_count=total_effect_count,
            disagreeing_resources=tuple(
                (
                    row["endpoint"],
                    row["target"],
                    int(row["effect_count"]),
                    int(row["ledger_rows"]),
                )
                for row in disagreeing
            ),
        )
