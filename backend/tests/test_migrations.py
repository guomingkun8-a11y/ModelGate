from __future__ import annotations

import pytest

from app.persistence.db import BASE_TABLES, legacy_revision
from app.persistence.models import Base


def test_detects_complete_current_unversioned_schema():
    tables = set(Base.metadata.tables)
    columns = {
        table: {column.name for column in Base.metadata.tables[table].columns}
        for table in tables
    }

    assert legacy_revision(tables, columns) == "head"


def test_detects_complete_legacy_unversioned_schema():
    tables = set(BASE_TABLES)
    columns = {
        table: {column.name for column in Base.metadata.tables[table].columns} - {"owner_id"}
        for table in tables
    }

    assert legacy_revision(tables, columns) == "0001_initial"


def test_leaves_empty_database_unstamped():
    assert legacy_revision(set(), {}) is None


def test_rejects_partial_unversioned_schema():
    with pytest.raises(RuntimeError, match="incomplete unversioned schema"):
        legacy_revision({"virtual_keys"}, {"virtual_keys": {"id"}})
