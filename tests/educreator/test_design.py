"""design の段（A13）のテスト。"""

import pytest

from educreator.design import build, cell, discover

FLASK_ROUTES = """
from flask import Blueprint, render_template, redirect

task_bp = Blueprint("task", __name__, url_prefix="/tasks")


def _render_list(mine):
    return render_template("task/list.html", mine=mine)


@task_bp.route("/")
def list_tasks():
    return _render_list(False)


@task_bp.route("/<int:task_id>", methods=["GET", "POST"])
@task_bp.route("/<int:task_id>/")
def detail(task_id):
    return render_template("task/detail.html")


@task_bp.route("/<int:task_id>/delete", methods=["POST"])
def delete(task_id):
    return redirect("/")
"""


def test_decorator_routes_follow_helpers_and_count_rules(tmp_path):
    (tmp_path / "task.py").write_text(FLASK_ROUTES, encoding="utf-8")
    routes = {r.endpoint: r for r in discover("decorator-routes", tmp_path)}
    assert routes["task.list_tasks"].screen == "task/list.html"  # 補助関数を1段たどる
    assert routes["task.detail"].rules == ("/tasks/<int:task_id>", "/tasks/<int:task_id>/")
    assert routes["task.detail"].methods == ("GET", "POST")
    assert routes["task.delete"].screen is None


def test_next_app_routes_strip_groups_and_name_dynamic_segments(tmp_path):
    for p in (
        "page.tsx",
        "(auth)/login/page.tsx",
        "user/[id]/edit/page.tsx",
        "api/trpc/[trpc]/route.ts",
    ):
        f = tmp_path / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("export default function P() {}", encoding="utf-8")
    routes = {r.endpoint: r for r in discover("page-files", tmp_path)}
    assert set(routes) == {"/", "/login", "/user/<id>/edit", "api:/api/trpc/<trpc>"}
    assert routes["api:/api/trpc/<trpc>"].screen is None


def test_unwritten_roles_are_blank_cells(tmp_path):
    (tmp_path / "task.py").write_text(FLASK_ROUTES, encoding="utf-8")
    routes = discover("decorator-routes", tmp_path)
    m = build(routes, None)
    # 画面2つ × 役割5 × 状態5 がすべて空き（R-1 で落ちる）
    assert m.stats["screens"] == 2 and m.stats["blank"] == 50 and m.stats["need"] == 0

    access = {
        "routes": [
            {
                "endpoint": "task.list_tasks",
                "roles": dict.fromkeys(["admin", "owner", "member", "outsider", "anon"], "show"),
                "states": ["empty"],
            },
            {
                "endpoint": "task.detail",
                "roles": {
                    "admin": "show",
                    "owner": "show",
                    "member": "deny:task.list_tasks",
                    "outsider": "403",
                    "anon": "login",
                },
            },
        ]
    }
    m = build(routes, access)
    assert m.stats["blank"] == 0
    # list: 5役割 × (通常+空) = 10、detail: 2役割 × 通常 = 2
    assert m.stats["need"] == 12


def test_access_for_unknown_route_is_an_error(tmp_path):
    (tmp_path / "task.py").write_text(FLASK_ROUTES, encoding="utf-8")
    with pytest.raises(ValueError, match=r"task\.gone"):
        build(
            discover("decorator-routes", tmp_path),
            {"routes": [{"endpoint": "task.gone", "roles": {}}]},
        )


def test_cell_conditional_role():
    text, kind = cell("show:担当者だけ。それ以外は deny:task.detail", "denied", [])
    assert kind == "na" and "task.detail" in text
    with pytest.raises(ValueError):
        cell("allow", "normal", [])
