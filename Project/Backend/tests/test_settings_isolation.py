"""Settings must never leak between tenants.

Before these were workspace-scoped, `settings` was one global key/value table:
one customer changing their daily limit or working hours changed it for every
other customer. These tests pin that down.
"""
from backend.database import (
    DEFAULT_WORKSPACE_SETTINGS,
    Setting,
    get_system_setting,
    get_workspace_settings,
    set_system_setting,
    set_workspace_setting,
)


def test_defaults_apply_to_a_workspace_that_never_saved(db, workspaces):
    a, _ = workspaces
    assert get_workspace_settings(db, a.id) == DEFAULT_WORKSPACE_SETTINGS


def test_one_tenant_cannot_change_another_tenants_limits(db, workspaces):
    a, b = workspaces

    set_workspace_setting(db, a.id, "daily_limit", "500")
    set_workspace_setting(db, a.id, "working_hours_start", "02:00")
    db.commit()

    assert get_workspace_settings(db, a.id)["daily_limit"] == "500"
    assert get_workspace_settings(db, a.id)["working_hours_start"] == "02:00"

    # Tenant B is untouched and still on the platform defaults.
    assert get_workspace_settings(db, b.id)["daily_limit"] == DEFAULT_WORKSPACE_SETTINGS["daily_limit"]
    assert get_workspace_settings(db, b.id)["working_hours_start"] == DEFAULT_WORKSPACE_SETTINGS["working_hours_start"]


def test_opt_out_keywords_are_per_tenant(db, workspaces):
    a, b = workspaces

    set_workspace_setting(db, a.id, "opt_out_keywords", "go away, remove me")
    db.commit()

    assert get_workspace_settings(db, a.id)["opt_out_keywords"] == "go away, remove me"
    assert get_workspace_settings(db, b.id)["opt_out_keywords"] == DEFAULT_WORKSPACE_SETTINGS["opt_out_keywords"]


def test_updating_a_setting_twice_does_not_create_duplicate_rows(db, workspaces):
    a, _ = workspaces

    set_workspace_setting(db, a.id, "daily_limit", "40")
    db.commit()
    set_workspace_setting(db, a.id, "daily_limit", "60")
    db.commit()

    rows = db.query(Setting).filter(
        Setting.workspace_id == a.id, Setting.key == "daily_limit"
    ).all()
    assert len(rows) == 1
    assert rows[0].value == "60"


def test_system_settings_stay_global(db, workspaces):
    a, _ = workspaces

    set_system_setting(db, "status", "running")
    db.commit()

    assert get_system_setting(db, "status") == "running"
    # The engine switch is not a per-workspace key and must not appear as one.
    assert "status" not in get_workspace_settings(db, a.id)

    set_system_setting(db, "status", "stopped")
    db.commit()
    assert get_system_setting(db, "status") == "stopped"


def test_deleting_a_workspace_removes_only_its_settings(db, workspaces):
    from backend.database import Workspace

    a, b = workspaces
    set_workspace_setting(db, a.id, "daily_limit", "11")
    set_workspace_setting(db, b.id, "daily_limit", "22")
    db.commit()

    doomed = Workspace(name="Temp", slug="temp-doomed-workspace")
    db.add(doomed)
    db.commit()
    set_workspace_setting(db, doomed.id, "daily_limit", "99")
    db.commit()

    db.delete(doomed)
    db.commit()

    assert get_workspace_settings(db, a.id)["daily_limit"] == "11"
    assert get_workspace_settings(db, b.id)["daily_limit"] == "22"


def test_workspace_deletion_cascades_to_tenant_data(db):
    """The workspace_id columns were added without a foreign key, so
    ON DELETE CASCADE never fired and deleting a workspace left tenant rows
    orphaned. Guard against that regressing."""
    from backend.database import MessageTemplate, OptOut, Setting, User, Workspace

    user = User(username="cascade_probe", email="cascade@example.com", password_hash="x")
    workspace = Workspace(name="Doomed", slug="doomed-cascade-probe")
    db.add_all([user, workspace])
    db.commit()

    db.add_all([
        MessageTemplate(name="t", content="c", user_id=user.id, workspace_id=workspace.id),
        OptOut(username="someone", user_id=user.id, workspace_id=workspace.id),
        Setting(workspace_id=workspace.id, key="daily_limit", value="9"),
    ])
    db.commit()
    workspace_id = workspace.id

    db.delete(workspace)
    db.commit()
    db.expire_all()

    assert db.query(MessageTemplate).filter_by(workspace_id=workspace_id).count() == 0
    assert db.query(OptOut).filter_by(workspace_id=workspace_id).count() == 0
    assert db.query(Setting).filter_by(workspace_id=workspace_id).count() == 0

    db.delete(user)
    db.commit()
